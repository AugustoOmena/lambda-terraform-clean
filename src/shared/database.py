import os

from aws_lambda_powertools import Logger
from supabase import create_client, Client

from shared.supabase_utils import jwt_role_from_supabase_key

_client: Client = None
_logger = Logger(service="supabase-client")


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
        role_hint = jwt_role_from_supabase_key(key)
        if role_hint == "anon":
            _logger.warning(
                "SUPABASE_KEY JWT indica role anon; o backoffice precisa da chave service_role (Settings → API)."
            )
        _client = create_client(url, key)
    return _client