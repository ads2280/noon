"""Repository for calendar-related database operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List

from postgrest import APIError

from db.session import get_service_client
from utils.errors import SupabaseStorageError


def _without_none(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove None values from dict."""
    return {key: value for key, value in data.items() if value is not None}


class CalendarRepository:
    """Repository for calendar database operations."""

    def get_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all Google accounts for a user."""
        client = get_service_client()
        try:
            result = (
                client.table("google_accounts").select("*").eq("user_id", user_id).execute()
            )
        except APIError as exc:
            raise SupabaseStorageError(exc.message) from exc
        return result.data or []

    def get_calendars(self, user_id: str, include_hidden: bool = False) -> List[Dict[str, Any]]:
        """
        Get all calendars for a user from the database.
        
        Args:
            user_id: User ID
            include_hidden: If False (default), filter out hidden calendars. If True, return all calendars.
        
        Returns:
            List of calendar dictionaries
        """
        client = get_service_client()
        try:
            query = client.table("calendars").select("*").eq("user_id", user_id)
            if not include_hidden:
                query = query.eq("is_hidden", False)
            result = query.execute()
        except APIError as exc:
            raise SupabaseStorageError(exc.message) from exc
        return result.data or []

    def get_calendars_by_account(self, google_account_id: str, include_hidden: bool = False) -> List[Dict[str, Any]]:
        """
        Get all calendars for a specific Google account.
        
        Args:
            google_account_id: Google account ID
            include_hidden: If False (default), filter out hidden calendars. If True, return all calendars.
        
        Returns:
            List of calendar dictionaries
        """
        client = get_service_client()
        try:
            query = (
                client.table("calendars")
                .select("*")
                .eq("google_account_id", google_account_id)
            )
            if not include_hidden:
                query = query.eq("is_hidden", False)
            result = query.execute()
        except APIError as exc:
            raise SupabaseStorageError(exc.message) from exc
        return result.data or []

    async def get_account(self, user_id: str) -> Dict[str, Any] | None:
        """
        Get the first Google account for a user.

        Args:
            user_id: Supabase user ID

        Returns:
            Google account dict with tokens, or None if no account linked
        """
        client = get_service_client()
        try:
            result = (
                client.table("google_accounts")
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise SupabaseStorageError(exc.message) from exc

        if not result.data:
            return None

        account = result.data[0]
        # Return account with tokens structure expected by agent
        return {
            "id": account.get("id"),
            "email": account.get("email"),
            "tokens": {
                "access_token": account.get("access_token"),
                "refresh_token": account.get("refresh_token"),
                "expires_at": account.get("expires_at"),
                "token_type": account.get("metadata", {}).get("token_type", "Bearer"),
            },
        }

    def upsert_account(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert a Google account."""
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

    def update_account(
        self, user_id: str, account_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a Google account."""
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

    def delete_account(self, user_id: str, account_id: str) -> None:
        """Delete a Google account and its calendars."""
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

        # Calendars will be automatically deleted via CASCADE when the account is deleted
        # But we can also explicitly delete them for clarity
        try:
            client.table("calendars").delete().eq("google_account_id", account_id).execute()
        except APIError as exc:
            raise SupabaseStorageError(f"Failed to clear calendars: {exc.message}") from exc

    def sync_calendars(self, google_account_id: str, calendars: Iterable[Dict[str, Any]]) -> None:
        """
        Upsert Google calendars for the account and remove stale entries.

        Args:
            google_account_id: Google account ID
            calendars: Iterable of calendar dictionaries with keys:
                - id (str): Google calendar ID
                - summary (str): Calendar display name
                - primary (bool): Whether this is the primary calendar
                - accessRole (str): Google Calendar access role ("reader", "writer", "owner")
                - backgroundColor (str | None): Hex color provided by Google (camelCase)
                - foregroundColor (str | None): Hex color provided by Google (camelCase)
        """
        # Fetch the account to get user_id for RLS
        client = get_service_client()
        try:
            account_result = (
                client.table("google_accounts")
                .select("user_id")
                .eq("id", google_account_id)
                .limit(1)
                .execute()
            )
        except APIError as exc:
            raise SupabaseStorageError(exc.message) from exc
        
        if not account_result.data:
            raise SupabaseStorageError(f"Google account {google_account_id} not found.")
        
        user_id = account_result.data[0]["user_id"]

        # Get existing calendars to preserve is_hidden values
        try:
            existing_calendars_result = (
                client.table("calendars")
                .select("google_calendar_id, is_hidden")
                .eq("google_account_id", google_account_id)
                .execute()
            )
            existing_calendars = {
                cal["google_calendar_id"]: cal.get("is_hidden", False)
                for cal in (existing_calendars_result.data or [])
            }
        except APIError as exc:
            # If we can't fetch existing calendars, proceed without preserving is_hidden
            existing_calendars = {}

        normalized: List[Dict[str, Any]] = []
        for calendar in calendars:
            google_id = calendar.get("id")
            if not google_id:
                continue

            # Preserve is_hidden for existing calendars, default to False for new ones
            is_hidden = existing_calendars.get(google_id, False)

            normalized.append(
                _without_none(
                    {
                        "user_id": user_id,
                        "google_account_id": google_account_id,
                        "google_calendar_id": google_id,
                        "name": calendar.get("summary") or google_id,
                        "description": calendar.get("description"),
                        "color": calendar.get("backgroundColor")
                        or calendar.get("foregroundColor"),
                        "is_primary": bool(calendar.get("primary", False)),
                        "access_role": calendar.get("accessRole"),  # Google API uses camelCase "accessRole"
                        "is_hidden": is_hidden,  # Preserve existing is_hidden value
                    }
                )
            )

        try:
            if normalized:
                client.table("calendars").upsert(
                    normalized, on_conflict="google_account_id,google_calendar_id"
                ).execute()
            # Remove calendars that are no longer present for this account
            google_ids = [row["google_calendar_id"] for row in normalized]
            delete_query = client.table("calendars").delete().eq("google_account_id", google_account_id)
            if google_ids:
                delete_query = delete_query.not_.in_("google_calendar_id", google_ids)
            response = delete_query.execute()
            # Supabase returns deleted rows when data present; no further checks needed
            _ = response.data
        except APIError as exc:
            raise SupabaseStorageError(exc.message) from exc

    def update_account_tokens(
        self,
        user_id: str,
        account_id: str,
        *,
        access_token: str,
        refresh_token: str | None,
        expires_at: datetime | None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Update Google account tokens."""
        client = get_service_client()
        payload = _without_none(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "metadata": metadata,
            }
        )
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
            raise SupabaseStorageError(
                "Google account tokens could not be updated or account not found."
            )
        return result.data[0]

    def update_calendar(
        self, user_id: str, calendar_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a calendar's properties.
        
        Args:
            user_id: User ID (for RLS validation)
            calendar_id: Calendar ID (UUID from database)
            data: Dictionary of fields to update (e.g., {"is_hidden": True})
        
        Returns:
            Updated calendar dictionary
        
        Raises:
            SupabaseStorageError: If calendar not found or update failed
        """
        client = get_service_client()
        payload = _without_none(data)
        if not payload:
            raise SupabaseStorageError("No fields provided to update.")
        
        try:
            result = (
                client.table("calendars")
                .update(payload)
                .eq("user_id", user_id)  # RLS ensures user owns the calendar
                .eq("id", calendar_id)
                .execute()
            )
        except APIError as exc:
            raise SupabaseStorageError(exc.message) from exc
        
        if not result.data:
            raise SupabaseStorageError("Calendar not found or update failed.")
        return result.data[0]
