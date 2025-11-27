# payments/webhooks/midtrans/disbursement.py
import aiohttp
import logging
import os
import uuid
import re
from lib.supabase_client import supabase

logger = logging.getLogger(__name__)

# 📌 Environment variable Midtrans
MIDTRANS_DISBURSEMENT_KEY = os.getenv("MIDTRANS_DISBURSEMENT_KEY")
# Lo bisa switch ke production nanti tinggal ganti URL
MIDTRANS_BASE_URL = os.getenv("MIDTRANS_BASE_URL", "https://app.sandbox.midtrans.com/iris/api/v1/payouts")

# 📌 Mapping bank/e-wallet sesuai IRIS
BANK_MAP = {
    "BCA": "bca",
    "BNI": "bni",
    "BRI": "bri",
    "MANDIRI": "mandiri",
    "BTN": "btn",
    "CIMB": "cimb",
    "PERMATA": "permata",
    "MAYBANK": "maybank",
    "OCBC": "ocbc",
    "UOB": "uob",
    "BSI": "bsi",
    "DANAMON": "danamon",
    "SEABANK": "seabank",
    "JAGO": "jago",
    "MUAMALAT": "muamalat",
    # E-Wallets
    "DANA": "dana",
    "OVO": "ovo",        # khusus OVO → harus di-handle custom
    "GOPAY": "gopay",
}

async def disburse(order: dict):
    """
    Kirim payout ke user via Midtrans IRIS.
    order dict harus ada:
      payout_name, payout_account, payout_bank, amount_idr, token, order_id, id
    """
    bank_code = BANK_MAP.get(order["payout_bank"].upper())
    if not bank_code:
        error_msg = f"Bank {order['payout_bank']} belum support di Midtrans"
        logger.error(f"❌ {error_msg}")
        supabase.table("TransactionsJual").update({
            "payout_status": "failed",
            "payout_error": error_msg,
            "status": "failed"
        }).eq("id", order["id"]).execute()
        return False

    # 📌 Special handling untuk OVO
    if bank_code == "ovo":
        bank_code = "cimb_va"  # Midtrans butuh cimb_va untuk OVO
        order["payout_account"] = f"8099{order['payout_account']}"

    # Idempotency key supaya request aman dari duplikat
    idempotency_key = str(uuid.uuid4())

    # Bersihkan token dan order_id dari karakter ilegal di notes
    token_clean = re.sub(r'[^A-Za-z0-9 ]+', '', order['token'])
    order_id_clean = re.sub(r'[^A-Za-z0-9 ]+', '', order['order_id'])
    notes_clean = f"WD Crypto {token_clean} Order {order_id_clean}"

    payload = {
        "payouts": [
            {
                "beneficiary_name": order["payout_name"],
                "beneficiary_account": order["payout_account"],
                "beneficiary_bank": bank_code,
                "amount": order["amount_idr"],
                "notes": notes_clean
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Idempotency-Key": idempotency_key
    }

    auth = aiohttp.BasicAuth(MIDTRANS_DISBURSEMENT_KEY, "")
    async with aiohttp.ClientSession(auth=auth) as session:
        try:
            async with session.post(MIDTRANS_BASE_URL, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status in (200, 201):
                    # Ambil reference_no dari Midtrans (sandbox & production)
                    payout_ref = data["payouts"][0].get("reference_no")
                    logger.info(f"✅ Midtrans payout queued: {payout_ref}")

                    # Update DB dengan reference_no asli, jangan pakai dummy
                    supabase.table("TransactionsJual").update({
                        "midtrans_ref_id": payout_ref,  # <- kunci untuk webhook nanti
                        "payout_status": "queued",
                        "status": "waiting_callback",
                        "payout_error": None
                    }).eq("id", order["id"]).execute()
                    return True
                else:
                    error_msg = str(data)
                    logger.error(f"❌ Gagal request Midtrans: {resp.status} {error_msg}")
                    supabase.table("TransactionsJual").update({
                        "payout_status": "failed",
                        "payout_error": error_msg,
                        "status": "failed"
                    }).eq("id", order["id"]).execute()
                    return False
        except Exception as e:
            logger.exception(f"❌ Exception saat request payout: {e}")
            supabase.table("TransactionsJual").update({
                "payout_status": "failed",
                "payout_error": str(e),
                "status": "failed"
            }).eq("id", order["id"]).execute()
            return False
