# 📍 payments/webhooks/flip/disbursement.py
import os
import logging
import aiohttp
import base64
import uuid
from datetime import datetime
from lib.supabase_client import supabase

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s %(name)s]: %(message)s")

# ================= Flip Config =================
FLIP_SECRET_KEY = os.getenv("FLIP_SECRET_KEY")
FLIP_ENV = os.getenv("FLIP_ENV", "sandbox")  # 'sandbox' atau 'production'
BASE_URL = "https://bigflip.id/api" if FLIP_ENV == "production" else "https://bigflip.id/big_sandbox_api"

# ================= Auth Header =================
auth_string = base64.b64encode(f"{FLIP_SECRET_KEY}:".encode()).decode()

# ================= Helper =================
async def _post(endpoint: str, data: dict, extra_headers: dict = None):
    url = f"{BASE_URL}/{endpoint}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_string}"
    }
    if extra_headers:
        headers.update(extra_headers)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as resp:
            res = await resp.json()
            logger.info("POST %s | Status: %s | Response: %s", endpoint, resp.status, res)
            return res


async def _get(endpoint: str):
    url = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Basic {auth_string}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            res = await resp.json()
            # ✨ Jangan tampilkan full response untuk list bank
            if endpoint == "v2/general/banks":
                logger.info("GET %s | Status: %s | Response: <hidden bank list>", endpoint, resp.status)
            else:
                logger.info("GET %s | Status: %s | Response: %s", endpoint, resp.status, res)
            return res

# ================= Bank List =================
async def get_banks():
    """
    Ambil daftar bank Flip terbaru.
    """
    res = await _get("v2/general/banks")
    return res  # List of dict

async def resolve_bank_code(bank_name: str):
    """
    Cari bank_code dari nama bank.
    """
    banks = await get_banks()
    bank_name_upper = bank_name.upper()
    for b in banks:
        if b["name"].upper() == bank_name_upper:
            return b["bank_code"]
    return None

# ================= Bank Account Inquiry =================
async def check_account(order: dict):
    bank_code = await resolve_bank_code(order.get("payout_bank", ""))
    if not bank_code:
        return {"status": "INVALID_BANK", "error": f"Bank {order.get('payout_bank')} belum support"}

    inquiry_key = str(uuid.uuid4())
    data = {
        "bank_code": bank_code,
        "account_number": order.get("payout_account"),
        "inquiry_key": inquiry_key
    }
    res = await _post("v2/disbursement/bank-account-inquiry", data)
    return res

# ================= Adapter disburse =================
async def disburse(order: dict):
    try:
        # ===== Cek rekening dulu =====
        account_res = await check_account(order)
        acc_status = account_res.get("status")
        if acc_status not in ("SUCCESS", "SUSPECTED_ACCOUNT"):
            if FLIP_ENV == "sandbox" and acc_status == "PENDING":
                logger.info(f"ℹ️ Sandbox mode: rekening masih PENDING, lanjutkan disburse")
            else:
                error_msg = account_res.get("error") or f"Inquiry failed: {acc_status}"
                logger.error(f"❌ Rekening invalid / blacklisted: {acc_status}")
                supabase.table("TransactionsJual").update({
                    "payout_status": acc_status.lower(),
                    "payout_error": error_msg,
                    "status": "failed"
                }).eq("id", order["id"]).execute()
                return False

        bank_code = await resolve_bank_code(order.get("payout_bank", ""))
        if not bank_code:
            logger.error(f"❌ Bank {order.get('payout_bank')} tidak ditemukan di Flip")
            supabase.table("TransactionsJual").update({
                "payout_status": "failed",
                "payout_error": f"Bank {order.get('payout_bank')} tidak ditemukan",
                "status": "failed"
            }).eq("id", order["id"]).execute()
            return False

        idempotency_key = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        remark = f"WD {order.get('token')} {order.get('order_id')}"[:18]

        data = {
            "bank_code": bank_code,
            "account_number": order.get("payout_account"),
            "amount": str(order.get("amount_idr", 0)),
            "remark": remark
        }

        extra_headers = {
            "idempotency-key": idempotency_key,
            "X-TIMESTAMP": timestamp
        }

        # ===== Disbursement =====
        res = await _post("v3/disbursement", data, extra_headers)

        disb_id = res.get("id") or str(uuid.uuid4())
        status = res.get("status", "pending")
        supabase.table("TransactionsJual").update({
            "flip_ref_id": disb_id,
            "payout_status": status,
            "status": "waiting_callback" if status in ("queued", "pending") else status,
            "payout_error": None if status in ("success","queued","pending") else str(res)
        }).eq("id", order["id"]).execute()

        logger.info(f"✅ Flip disbursement {status}: {disb_id}")
        return True if status in ("success","queued","pending") else False

    except Exception as e:
        logger.exception(f"❌ Exception saat Flip disbursement: {e}")
        supabase.table("TransactionsJual").update({
            "payout_status": "failed",
            "payout_error": str(e),
            "status": "failed"
        }).eq("id", order["id"]).execute()
        return False
