"""Centralized exception classes for the application."""

from __future__ import annotations

from typing import Any

from fastapi import status


# Supabase errors
class SupabaseAuthError(RuntimeError):
    """Raised when Supabase auth operations fail."""


class SupabaseStorageError(RuntimeError):
    """Raised when Supabase data operations fail."""


# Google OAuth errors
class GoogleOAuthError(RuntimeError):
    """Raised when Google OAuth flow fails."""


class GoogleStateError(RuntimeError):
    """Raised when the OAuth state token is invalid."""


# Google Calendar API errors
class GoogleCalendarAPIError(RuntimeError):
    """Raised when the Google Calendar REST API returns an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


# Google Calendar service errors
class GoogleCalendarServiceError(RuntimeError):
    """Base error for Google Calendar service issues."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class GoogleCalendarUserError(GoogleCalendarServiceError):
    """Raised when a user-precondition fails."""

    status_code = status.HTTP_400_BAD_REQUEST


class GoogleCalendarAuthError(GoogleCalendarServiceError):
    """Raised when Google authentication fails."""

    status_code = status.HTTP_401_UNAUTHORIZED


class GoogleCalendarEventNotFoundError(GoogleCalendarServiceError):
    """Raised when the target event cannot be located."""

    status_code = status.HTTP_404_NOT_FOUND
