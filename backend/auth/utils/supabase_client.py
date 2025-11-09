from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Iterable, List, Tuple

import jwt
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


def _without_none(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def send_phone_otp(phone: str) -> None:
    client = get_service_client()
    try:
        client.auth.sign_in_with_otp({"phone": phone})
    except Exception as exc:  # pragma: no cover - supabase raises dynamic errors
        raise SupabaseAuthError(str(exc)) from exc


def verify_phone_otp(phone: str, token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    client = get_service_client()
    try:
        response = client.auth.verify_otp(
            {"phone": phone, "token": token, "type": "sms"}
        )
    except Exception as exc:  # pragma: no cover
        raise SupabaseAuthError(str(exc)) from exc

    session = _model_dump(getattr(response, "session", None))
    user = _model_dump(getattr(response, "user", None))

    if not session or not user:
        raise SupabaseAuthError("Supabase did not return a valid session or user.")

    return session, user


def refresh_session(refresh_token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    client = get_service_client()
    try:
        response = client.auth.refresh_session(refresh_token)
    except Exception as exc:  # pragma: no cover - supabase raises dynamic errors
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


async def get_user_from_token(access_token: str) -> Dict[str, Any]:
    """
    Validate JWT access token and retrieve user information from database.

    Args:
        access_token: Supabase JWT access token

    Returns:
        User dictionary with id, phone, created_at, updated_at

    Raises:
        SupabaseAuthError: If token is invalid, expired, or user not found
    """
    settings = get_settings()

    if not settings.supabase_jwt_secret:
        raise SupabaseAuthError("JWT secret not configured")

    try:
        # Decode and validate JWT token
        decoded = jwt.decode(
            access_token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = decoded.get("sub")
        if not user_id:
            raise SupabaseAuthError("Invalid token: missing user ID")
    except jwt.ExpiredSignatureError:
        raise SupabaseAuthError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise SupabaseAuthError(f"Invalid token: {str(exc)}") from exc

    # Fetch user from database
    client = get_service_client()
    try:
        result = client.table("users").select("*").eq("id", user_id).execute()
    except APIError as exc:
        raise SupabaseStorageError(f"Failed to fetch user: {exc.message}") from exc

    if not result.data:
        raise SupabaseAuthError("User not found")

    user = result.data[0]
    return user


def list_google_accounts(user_id: str) -> List[Dict[str, Any]]:
    client = get_service_client()
    try:
        result = (
            client.table("google_accounts").select("*").eq("user_id", user_id).execute()
        )
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc
    return result.data or []


def upsert_google_account(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    client = get_service_client()
    payload = _without_none({"user_id": user_id, **data})
    try:
        result = (
            client.table("google_accounts")
            .upsert(payload, on_conflict="user_id,google_user_id")
            .execute()
        )
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc
    if not result.data:
        raise SupabaseStorageError(
            "Supabase did not return inserted google account data."
        )
    return result.data[0]


def update_google_account(
    user_id: str, account_id: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    client = get_service_client()
    payload = _without_none(data)
    try:
        result = (
            client.table("google_accounts")
            .update(payload)
            .eq("user_id", user_id)
            .eq("id", account_id)
            .execute()
        )
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc
    if not result.data:
        raise SupabaseStorageError("Google account not found or update failed.")
    return result.data[0]


def delete_google_account(user_id: str, account_id: str) -> None:
    client = get_service_client()
    try:
        response = (
            client.table("google_accounts")
            .delete()
            .eq("user_id", user_id)
            .eq("id", account_id)
            .execute()
        )
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc

    if not response.data:
        raise SupabaseStorageError("Google account not found or already removed.")

    try:
        client.table("calendars").delete().eq("user_id", user_id).execute()
    except APIError as exc:
        raise SupabaseStorageError(f"Failed to clear calendars: {exc.message}") from exc


def sync_google_calendars(
    user_id: str, calendars: Iterable[Dict[str, Any]]
) -> None:
    """
    Upsert Google calendars for the user and remove stale entries.

    Args:
        user_id: Supabase user ID
        calendars: Iterable of calendar dictionaries with keys:
            - id (str): Google calendar ID
            - summary (str): Calendar display name
            - primary (bool): Whether this is the primary calendar
            - background_color (str | None): Hex color provided by Google
    """

    normalized: List[Dict[str, Any]] = []
    for calendar in calendars:
        google_id = calendar.get("id")
        if not google_id:
            continue

        normalized.append(
            _without_none(
                {
                    "user_id": user_id,
                    "google_calendar_id": google_id,
                    "name": calendar.get("summary") or google_id,
                    "description": calendar.get("description"),
                    "color": calendar.get("background_color")
                    or calendar.get("foreground_color"),
                    "is_primary": bool(calendar.get("primary", False)),
                }
            )
        )

    client = get_service_client()

    try:
        if normalized:
            client.table("calendars").upsert(
                normalized, on_conflict="user_id,google_calendar_id"
            ).execute()
        # Remove calendars that are no longer present
        google_ids = [row["google_calendar_id"] for row in normalized]
        delete_query = client.table("calendars").delete().eq("user_id", user_id)
        if google_ids:
            delete_query = delete_query.not_.in_("google_calendar_id", google_ids)
        response = delete_query.execute()
        # Supabase returns deleted rows when data present; no further checks needed
        _ = response.data
    except APIError as exc:
        raise SupabaseStorageError(exc.message) from exc
