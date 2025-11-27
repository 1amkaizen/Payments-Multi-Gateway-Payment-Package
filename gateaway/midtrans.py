# payments/gateaway/midtrans.py

import httpx
import base64
import logging
from config import MIDTRANS_SERVER_KEY, MIDTRANS_IS_PRODUCTION

logger = logging.getLogger(__name__)

MIDTRANS_URL = (
    "https://app.midtrans.com/snap/v1/transactions"
    if MIDTRANS_IS_PRODUCTION
    else "https://app.sandbox.midtrans.com/snap/v1/transactions"
)

if not MIDTRANS_SERVER_KEY:
    raise RuntimeError("❌ MIDTRANS_SERVER_KEY tidak ditemukan di .env")

basic_auth = base64.b64encode(f"{MIDTRANS_SERVER_KEY}:".encode()).decode()


async def create_midtrans_transaction(
    order_id: str,
    gross_amount: int,
    customer_name: str,
    customer_email: str,
    enabled_payments: list[str] | None = None,
):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Basic {basic_auth}",
    }

    payload = {
        "transaction_details": {"order_id": order_id, "gross_amount": gross_amount},
        "customer_details": {"first_name": customer_name, "email": customer_email},
        "enabled_payments": enabled_payments
        or ["gopay", "qris", "other_qris", "bank_transfer"],
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(MIDTRANS_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["redirect_url"], data
    except httpx.HTTPStatusError as e:
        logger.error(
            f"❌ Midtrans HTTP error: {e.response.status_code} - {e.response.text}"
        )
        raise RuntimeError(f"❌ Midtrans HTTP error: {e}")
    except Exception as e:
        logger.exception("❌ Gagal membuat transaksi Midtrans")
        raise RuntimeError(f"❌ Midtrans error: {e}")
