# 📍 payments/webhooks/flip/disbursement.py
from fastapi import APIRouter, Request, HTTPException
import logging
import os
import json
from lib.supabase_client import supabase

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

router = APIRouter()

# ================= Flip Config =================
FLIP_CALLBACK_TOKEN = os.getenv("FLIP_CALLBACK_TOKEN")


async def default_callback(tx, payload):
    """Callback default, bisa diganti saat import package"""
    logger.info(f"ℹ️ Default callback dipanggil untuk transaksi {tx['id']}")


@router.post("/disbursement/flip")
async def flip_disbursement_callback(request: Request, on_settlement=None):
    """
    Handler generic Flip Disbursement
    on_settlement: async callback(tx, payload) ketika payout sukses
    """
    try:
        form = await request.form()
        data = form.get("data")
        token = form.get("token")

        if not data or not token:
            logger.error("❌ Payload Flip callback invalid")
            raise HTTPException(status_code=400, detail="Invalid callback payload")

        # ✅ Verifikasi token callback
        if token != FLIP_CALLBACK_TOKEN:
            logger.warning("❌ Invalid callback token: %s", token)
            raise HTTPException(status_code=401, detail="Unauthorized callback")

        disbursement_data = json.loads(data)
        status = disbursement_data.get("status")  # DONE / CANCELLED
        disbursement_id = disbursement_data.get("id")

        logger.info(
            "📩 Flip Callback Received | ID: %s | Status: %s",
            disbursement_id,
            status,
        )

        # Ambil transaksi dari DB
        res = (
            supabase.table("Payouts")
            .select("*")
            .eq("flip_ref_id", disbursement_id)
            .execute()
        )
        if not res.data:
            logger.warning(
                f"❌ Transaksi dengan Flip ID {disbursement_id} tidak ditemukan di DB"
            )
            return {"status": "ok", "note": "transaction not found"}

        tx = res.data[0]
        new_status = "success" if status.upper() == "DONE" else "failed"

        # Update DB
        supabase.table("Payouts").update(
            {
                "status": new_status,
                "payout_status": "success" if new_status == "success" else "failed",
            }
        ).eq("id", tx["id"]).execute()

        # Jalankan callback opsional
        callback_fn = on_settlement or default_callback
        try:
            await callback_fn(tx, disbursement_data)
        except Exception as e:
            logger.error(f"❌ Gagal eksekusi callback: {e}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ Error processing Flip callback: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
