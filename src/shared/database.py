import os
from supabase import create_client, Client

_client: Client = None


def get_supabase_client() -> Client:
    """Singleton Supabase client for Lambdas.

    SUPABASE_KEY must be the **service_role** key so server-side queries are not
    blocked by RLS on tables like ``profiles``. The anon/public key often allows
    ``products`` reads while hiding ``profiles`` rows — backoffice then sees
    empty lists and failed admin checks.
    """
    global _client
    if not _client:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Configurações do Supabase ausentes (ENV VARS)")
        _client = create_client(url, key)
    return _client