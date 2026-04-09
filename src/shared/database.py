import os
from supabase import create_client, Client

_client: Client = None


def get_supabase_client() -> Client:
    """Singleton usado pelo servidor.

    Para **listar todos** os perfis (GET /usuarios), **SUPABASE_KEY** deve ser a chave
    **service_role** (RLS não bloqueia). Com apenas **anon**, a listagem fica vazia.

    Para **checar admin** no backoffice quando a Lambda só tem anon: use também
    **SUPABASE_ANON_KEY** + header **Authorization** Bearer (repositório chama o REST
    como o front faz).
    """
    global _client
    if not _client:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("Configurações do Supabase ausentes (ENV VARS)")
        _client = create_client(url, key)
    return _client