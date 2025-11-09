"""Supabase database client and connection management."""

from functools import lru_cache

from supabase import Client, create_client

from .config import get_settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Get cached Supabase client instance.

    Reads credentials from environment variables:
    - SUPABASE_URL: Your Supabase project URL
    - SUPABASE_KEY: Your Supabase anon or service key

    Returns:
        Supabase client instance
    """
    settings = get_settings()

    if not settings.supabase_url or not settings.supabase_key:
        raise ValueError(
            "Supabase credentials not configured. Set SUPABASE_URL and SUPABASE_KEY in .env file."
        )

    client = create_client(settings.supabase_url, settings.supabase_key)
    return client


def get_db() -> Client:
    """
    Get Supabase database client.

    Convenience wrapper around get_supabase_client for FastAPI dependency injection.

    Usage:
        @app.get("/users/{user_id}")
        async def get_user(user_id: str, db: Client = Depends(get_db)):
            result = db.table("users").select("*").eq("id", user_id).execute()
            return result.data
    """
    return get_supabase_client()
