# payments/webhooks/midtrans/payment.py
from fastapi import APIRouter, Request
from lib.supabase_client import supabase
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger("webhooks.midtrans")


@router.post("/midtrans")
async def midtrans_webhook(request: Request, on_settlement=None):
    """
    Webhook Midtrans generik
    on_settlement: callback async yang dipanggil saat transaction_status = 'settlement'
    """
    logger.info("📥 Endpoint /midtrans dipanggil!")

    try:
        body = await request.json()
        logger.info(f"📩 Webhook Midtrans diterima:\n{body}")

        order_id = body.get("order_id")
        if not order_id:
            logger.warning("⚠️ order_id tidak ditemukan dalam body!")
            return {"message": "order_id kosong"}

        transaction_status = body.get("transaction_status")
        settlement_time = body.get("settlement_time", datetime.utcnow().isoformat())

        # Update data transaksi di tabel Transactions
        update_data = {
            "transaction_status": transaction_status,
            "fraud_status": body.get("fraud_status"),
            "settlement_time": settlement_time,
            "transaction_id": body.get("transaction_id"),
            "payment_type": body.get("payment_type"),
            "currency": body.get("currency"),
            "transaction_time": body.get("transaction_time"),
            "status_message": body.get("status_message"),
            "signature_key": body.get("signature_key"),
            "merchant_id": body.get("merchant_id"),
        }

        # Ambil transaksi dari DB
        res = (
            supabase.table("Transactions")
            .select("*")
            .eq("order_id", order_id)
            .execute()
        )
        transaction = res.data[0] if res.data else None
        if not transaction:
            logger.warning(f"❌ Transaksi dengan order_id {order_id} tidak ditemukan.")
            return {"message": "Transaksi tidak ditemukan"}

        # Update transaksi
        supabase.table("Transactions").update(update_data).eq(
            "order_id", order_id
        ).execute()
        logger.info(f"📝 Transaksi {order_id} berhasil diupdate.")

        # Jalankan callback opsional jika settlement
        if transaction_status == "settlement" and on_settlement:
            await on_settlement(transaction, body)

        return {"message": "OK"}

    except Exception as e:
        logger.exception("❌ Gagal memproses webhook Midtrans")
        return {"message": f"Error: {e}"}
