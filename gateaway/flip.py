# payments/gateway/flip.py

import httpx
import logging
from config import FLIP_API_KEY, FLIP_IS_PRODUCTION

logger = logging.getLogger(__name__)

FLIP_URL = (
    "https://api.flip.id/v1" if FLIP_IS_PRODUCTION else "https://sandbox.flip.id/v1"
)

if not FLIP_API_KEY:
    raise RuntimeError("❌ FLIP_API_KEY tidak ditemukan di .env")


class FlipGateway:
    def __init__(self, api_key: str = FLIP_API_KEY):
        self.api_key = api_key
        self.base_url = FLIP_URL
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def create_transaction(
        self,
        order_id: str,
        amount: int,
        source_bank: str,
        destination_bank: str,
        account_number: str,
        account_name: str,
    ):
        """
        Buat transaksi Flip
        """
        payload = {
            "order_id": order_id,
            "amount": amount,
            "source_bank": source_bank,
            "destination_bank": destination_bank,
            "account_number": account_number,
            "account_name": account_name,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/transactions", headers=self.headers, json=payload
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ Flip transaction created: {data}")
                return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"❌ Flip HTTP error: {e.response.status_code} - {e.response.text}"
            )
            raise RuntimeError(f"❌ Flip HTTP error: {e}")
        except Exception as e:
            logger.exception("❌ Gagal membuat transaksi Flip")
            raise RuntimeError(f"❌ Flip error: {e}")

    async def get_transaction_status(self, transaction_id: str):
        """
        Cek status transaksi Flip
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/transactions/{transaction_id}",
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"ℹ️ Flip transaction status: {data}")
                return data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"❌ Flip HTTP error: {e.response.status_code} - {e.response.text}"
            )
            raise RuntimeError(f"❌ Flip HTTP error: {e}")
        except Exception as e:
            logger.exception("❌ Gagal ambil status transaksi Flip")
            raise RuntimeError(f"❌ Flip error: {e}")
