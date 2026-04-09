"""Helpers for Supabase (roles, REST com JWT do usuário)."""

from typing import Any, Optional

import requests


def normalize_profile_role(raw: Any) -> Optional[str]:
    """Return lowercase trimmed role string, or None if missing/empty."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if s else None


def fetch_profile_role_via_rest_with_user_jwt(
    supabase_url: str,
    anon_key: str,
    authorization_header: str,
    user_id: str,
    timeout_sec: float = 15.0,
) -> Optional[str]:
    """
    Mesma leitura que o front faz no PostgREST: apikey anon + Authorization Bearer (sessão).

    Usado quando SUPABASE_KEY na Lambda é anon: o client Python não envia o JWT do usuário,
    então o RLS não devolve linhas; com o Bearer do request, auth.uid() casa e a role aparece.
    """
    if not supabase_url or not anon_key or not user_id:
        return None
    auth = (authorization_header or "").strip()
    if not auth.lower().startswith("bearer "):
        return None
    url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
    try:
        r = requests.get(
            url,
            params={"select": "role", "id": f"eq.{user_id}"},
            headers={
                "apikey": anon_key,
                "Authorization": auth,
            },
            timeout=timeout_sec,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return normalize_profile_role(data[0].get("role"))
    except Exception:
        return None
    return None


def get_authorization_header(event: dict) -> Optional[str]:
    """Lê Authorization do evento HTTP API (API Gateway normaliza chaves em minúsculas)."""
    headers = event.get("headers") or {}
    for k, v in headers.items():
        if k.lower() == "authorization" and v:
            return str(v).strip()
    return None
