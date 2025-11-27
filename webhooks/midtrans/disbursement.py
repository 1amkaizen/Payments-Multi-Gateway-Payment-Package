# 📍 payments/webhooks/midtrans/disbursement.py
from fastapi import APIRouter, Request, HTTPException
from lib.supabase_client import supabase
import logging

logger = logging.getLogger("webhooks.disbursement")
router = APIRouter()


async def default_callback(tx, payload):
    """Callback default, bisa diganti saat import package"""
    logger.info(f"ℹ️ Default callback dipanggil untuk transaksi {tx['id']}")


@router.post("/disbursement/midtrans")
async def disbursement_webhook(request: Request, on_settlement=None):
    """
    Webhook generic untuk disbursement
    on_settlement: async callback(tx, payload) ketika payout sukses
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"❌ Payload invalid: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(f"📩 Webhook callback diterima: {payload}")

    # Ambil reference ID: production / sandbox
    midtrans_ref_id = (
        payload.get("id")
        or payload.get("disbursement_id")
        or payload.get("reference_no")
    )
    status = payload.get("status")  # success / pending / failed / test

    if not midtrans_ref_id or not status:
        logger.error("❌ Missing disbursement_id atau status di payload")
        raise HTTPException(status_code=400, detail="Missing required fields")

    if status.lower() == "test":
        status = "success"

    res = (
        supabase.table("Payouts")
        .select("*")
        .eq("midtrans_ref_id", midtrans_ref_id)
        .execute()
    )
    if not res.data:
        logger.warning(
            f"❌ Transaksi dengan ref {midtrans_ref_id} tidak ditemukan di DB"
        )
        if "test-reference" in midtrans_ref_id:
            logger.info(
                "ℹ️ Sandbox test, transaksi tidak ada di DB. Melewati update dan notif."
            )
            return {"status": "ok", "sandbox_test": True}
        raise HTTPException(status_code=404, detail="Order not found")

    tx = res.data[0]
    new_status = "success" if status.lower() == "success" else "failed"
    supabase.table("Payouts").update(
        {
            "status": new_status,
            "payout_status": "success" if new_status == "success" else "failed",
        }
    ).eq("id", tx["id"]).execute()

    # Jalankan callback opsional
    callback_fn = on_settlement or default_callback
    try:
        await callback_fn(tx, payload)
    except Exception as e:
        logger.error(f"❌ Gagal eksekusi callback: {e}")

    return {"status": "ok"}
