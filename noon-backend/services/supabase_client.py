from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from postgrest import APIError
from supabase import Client, create_client

from config import get_settings


class SupabaseAuthError(RuntimeError):
    """Raised when Supabase auth operations fail."""


class SupabaseStorageError(RuntimeError):
    """Raised when Supabase data operations fail."""


@lru_cache
def get_service_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _model_dump(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump()
    dict_fn = getattr(obj, "dict", None)
    if callable(dict_fn):
        return dict_fn()
    return obj.__dict__  # type: ignore[attr-defined]


def send_phone_otp(phone: str) -> None:
    client = get_service_client()
    try:
        client.auth.sign_in_with_otp({"phone": phone})
    except Exception as exc:  # pragma: no cover - supabase raises dynamic errors
        raise SupabaseAuthError(str(exc)) from exc


def verify_phone_otp(phone: str, token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    client = get_service_client()
    try:
        response = client.auth.verify_otp({"phone": phone, "token": token, "type": "sms"})
    except Exception as exc:  # pragma: no cover
        raise SupabaseAuthError(str(exc)) from exc

    session = _model_dump(getattr(response, "session", None))
    user = _model_dump(getattr(response, "user", None))

    if not session or not user:
        raise SupabaseAuthError("Supabase did not return a valid session or user.")

    return session, user


def ensure_user_profile(user: Dict[str, Any], phone: str) -> Dict[str, Any]:
    client = get_service_client()
    payload = {
        "id": user.get("id"),
        "phone": phone,
    }
    try:
        result = client.table("users").upsert(payload, on_conflict="id").execute()
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc

    return result.data[0] if result.data else payload


def list_google_accounts(user_id: str) -> List[Dict[str, Any]]:
    client = get_service_client()
    try:
        result = client.table("google_accounts").select("*").eq("user_id", user_id).execute()
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc
    return result.data or []


def upsert_google_account(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    client = get_service_client()
    payload = {"user_id": user_id, **data}
    try:
        result = client.table("google_accounts").upsert(payload, on_conflict="user_id,google_user_id").execute()
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc
    if not result.data:
        raise SupabaseStorageError("Supabase did not return inserted google account data.")
    return result.data[0]


def delete_google_account(user_id: str, account_id: str) -> None:
    client = get_service_client()
    try:
        response = client.table("google_accounts").delete().eq("user_id", user_id).eq("id", account_id).execute()
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc

    if not response.data:
        raise SupabaseStorageError("Google account not found or already removed.")

