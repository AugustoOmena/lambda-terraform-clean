import os
from supabase import create_client, Client

_client: Client = None


def get_supabase_client() -> Client:
    """Singleton usado pelo servidor.

    **CRUD com RLS (ex.: products):** defina **SUPABASE_SERVICE_ROLE_KEY** (service_role
    no dashboard Supabase). Com só **anon** em **SUPABASE_KEY**, inserts em tabelas
    protegidas falham (42501) porque o cliente PostgREST não é ``service_role``.

    Para **listar todos** os perfis (GET /usuarios), **SUPABASE_KEY** como service_role
    ou **SUPABASE_SERVICE_ROLE_KEY** preenchida evita listagem vazia por RLS.

    Backoffice com Lambda só **anon**: **SUPABASE_ANON_KEY** + ``Authorization: Bearer``
    (JWT do usuário), como no front.
    """
    global _client
    if not _client:
        url = os.environ.get("SUPABASE_URL")
        # Prefer explicit service role for backend lambdas.
        key = (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_KEY")
            or os.environ.get("SUPABASE_ANON_KEY")
        )
        if not url or not key:
            raise ValueError("Configurações do Supabase ausentes (ENV VARS)")
        _client = create_client(url, key)
    return _client