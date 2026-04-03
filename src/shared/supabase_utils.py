"""Helpers for Supabase-backed data (roles, etc.)."""

from typing import Any, Optional


def normalize_profile_role(raw: Any) -> Optional[str]:
    """Return lowercase trimmed role string, or None if missing/empty."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    return s if s else None
