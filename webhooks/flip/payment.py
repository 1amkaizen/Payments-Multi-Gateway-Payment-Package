# payments/webhooks/flip/payment.py
from fastapi import APIRouter, Request
from lib.supabase_client import supabase
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger("webhooks.flip")


@router.post("/flip")
async def flip_webhook(request: Request, on_status_change=None):
    """
    Webhook Flip generik
    on_status_change: callback async yang dipanggil saat status transaksi berubah
    """
    logger.info("📥 Endpoint /flip dipanggil!")

    try:
        body = await request.json()
        logger.info(f"📩 Webhook Flip diterima:\n{body}")

        transaction_id = body.get("id")
        if not transaction_id:
            logger.warning("⚠️ transaction_id tidak ditemukan dalam body!")
            return {"message": "transaction_id kosong"}

        transaction_status = body.get("status")
        transaction_time = body.get("created_at", datetime.utcnow().isoformat())

        # Update data transaksi di tabel Transactions
        update_data = {
            "transaction_status": transaction_status,
            "amount": body.get("amount"),
            "currency": body.get("currency"),
            "source_bank": body.get("source_bank"),
            "destination_bank": body.get("destination_bank"),
            "account_number": body.get("account_number"),
            "account_name": body.get("account_name"),
            "transaction_time": transaction_time,
        }

        # Ambil transaksi dari DB
        res = (
            supabase.table("Transactions")
            .select("*")
            .eq("transaction_id", transaction_id)
            .execute()
        )
        transaction = res.data[0] if res.data else None
        if not transaction:
            logger.warning(
                f"❌ Transaksi dengan transaction_id {transaction_id} tidak ditemukan."
            )
            return {"message": "Transaksi tidak ditemukan"}

        # Update transaksi
        supabase.table("Transactions").update(update_data).eq(
            "transaction_id", transaction_id
        ).execute()
        logger.info(f"📝 Transaksi {transaction_id} berhasil diupdate.")

        # Jalankan callback opsional
        if on_status_change:
            await on_status_change(transaction, body)

        return {"message": "OK"}

    except Exception as e:
        logger.exception("❌ Gagal memproses webhook Flip")
        return {"message": f"Error: {e}"}
