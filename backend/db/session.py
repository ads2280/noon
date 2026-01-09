"""Database session and client factory for Supabase."""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from core.config import get_settings


@lru_cache
def get_service_client() -> Client:
    """Get cached Supabase service client."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
