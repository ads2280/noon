"""Repository for authentication-related database operations."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from postgrest import APIError

from db.session import get_service_client
from utils.errors import SupabaseAuthError, SupabaseStorageError


def _model_dump(obj: Any) -> Dict[str, Any]:
    """Helper to convert object to dict."""
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


class AuthRepository:
    """Repository for authentication database operations."""

    def send_phone_otp(self, phone: str) -> None:
        """Send phone OTP."""
        client = get_service_client()
        try:
            client.auth.sign_in_with_otp({"phone": phone})
        except Exception as exc:  # pragma: no cover - supabase raises dynamic errors
            raise SupabaseAuthError(str(exc)) from exc

    def verify_phone_otp(self, phone: str, token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Verify phone OTP and return session and user."""
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

    def refresh_session(self, refresh_token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Refresh session using refresh token."""
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

    def ensure_user_profile(self, user: Dict[str, Any], phone: str) -> Dict[str, Any]:
        """Ensure user profile exists in database."""
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

    async def get_user_from_token(self, access_token: str) -> Dict[str, Any]:
        """
        Validate JWT access token and retrieve user information from database.

        Args:
            access_token: Supabase JWT access token

        Returns:
            User dictionary with id, phone, created_at, updated_at

        Raises:
            SupabaseAuthError: If token is invalid, expired, or user not found
        """
        from core.config import get_settings
        import jwt

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
            # Check if the error is related to JWT expiration
            # Supabase may return JWT errors even with service role key if RLS is checking
            error_message = str(exc.message).lower()
            if exc.code == "PGRST303" or "jwt expired" in error_message:
                raise SupabaseAuthError("Token has expired") from exc
            raise SupabaseStorageError(f"Failed to fetch user: {exc.message}") from exc

        if not result.data:
            raise SupabaseAuthError("User not found")

        return result.data[0]
