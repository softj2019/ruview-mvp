import os
from supabase import create_client, Client


_client: Client | None = None


def get_supabase() -> Client | None:
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        print("[supabase] No credentials found, running in offline mode")
        return None

    _client = create_client(url, key)
    return _client
