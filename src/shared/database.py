import os
from supabase import create_client, Client

_client: Client = None

def get_supabase_client() -> Client:
    global _client
    if not _client:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Configurações do Supabase ausentes (ENV VARS)")
        _client = create_client(url, key)
    return _client