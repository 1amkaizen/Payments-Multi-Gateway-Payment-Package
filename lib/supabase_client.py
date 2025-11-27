# 📍 File: lib/supabase_client.py

import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    raise RuntimeError(f"❌ Gagal menghubungkan ke Supabase: {e}")

def generate_public_url(bucket_name: str, file_path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_path}"
