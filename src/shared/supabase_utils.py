"""Helpers for Supabase-backed data (roles, etc.)."""

import base64
import json
from typing import Any, Optional


def normalize_profile_role(raw: Any) -> Optional[str]:
    """Return lowercase trimmed role string, or None if missing/empty."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if s else None


def jwt_role_from_supabase_key(key: str) -> Optional[str]:
    """Best-effort decode of JWT ``role`` claim (anon vs service_role) without verifying signature."""
    try:
        parts = key.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        r = payload.get("role")
        return str(r) if r is not None else None
    except Exception:
        return None


def role_from_auth_user_obj(user: Any) -> Optional[str]:
    """Reads role from Supabase Auth user (app_metadata / user_metadata)."""
    if user is None:
        return None
    app_meta: dict[str, Any] = {}
    user_meta: dict[str, Any] = {}
    if isinstance(user, dict):
        app_meta = user.get("app_metadata") or {}
        user_meta = user.get("user_metadata") or {}
    else:
        am = getattr(user, "app_metadata", None)
        um = getattr(user, "user_metadata", None)
        if isinstance(am, dict):
            app_meta = am
        if isinstance(um, dict):
            user_meta = um
    for meta in (app_meta, user_meta):
        if "role" in meta and meta["role"] is not None:
            return normalize_profile_role(meta["role"])
    return None
