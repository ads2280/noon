"""Service for authentication business logic."""

from __future__ import annotations

from typing import Dict, Any

from domains.auth.repository import AuthRepository
from domains.auth.schemas import (
    OTPRequest,
    OTPInitResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    SessionRefreshRequest,
    OTPSession,
    UserProfile,
)
from utils.errors import SupabaseAuthError, SupabaseStorageError


class AuthService:
    """Service for authentication operations."""

    def __init__(self, repository: AuthRepository | None = None):
        """Initialize auth service with repository."""
        self.repository = repository or AuthRepository()

    def request_otp(self, data: OTPRequest) -> OTPInitResponse:
        """
        Request OTP to be sent to phone number.

        Args:
            data: OTP request with phone number

        Returns:
            OTP init response

        Raises:
            SupabaseAuthError: If OTP request fails
        """
        try:
            self.repository.send_phone_otp(data.phone)
        except SupabaseAuthError:
            raise
        return OTPInitResponse()

    def verify_otp(self, data: OTPVerifyRequest) -> OTPVerifyResponse:
        """
        Verify OTP code and create/update user profile.

        Args:
            data: OTP verify request with phone and code

        Returns:
            OTP verify response with session and user

        Raises:
            SupabaseAuthError: If OTP verification fails
            SupabaseStorageError: If user profile creation fails
        """
        try:
            session, user = self.repository.verify_phone_otp(data.phone, data.code)
        except SupabaseAuthError:
            raise

        try:
            self.repository.ensure_user_profile(user, data.phone)
        except SupabaseStorageError:
            raise

        return OTPVerifyResponse(
            session=OTPSession(
                access_token=session.get("access_token"),
                refresh_token=session.get("refresh_token"),
                token_type=session.get("token_type", "bearer"),
                expires_in=session.get("expires_in"),
            ),
            user=UserProfile(
                id=user.get("id"),
                phone=user.get("phone"),
            ),
        )

    def refresh_session(self, data: SessionRefreshRequest) -> OTPVerifyResponse:
        """
        Refresh session using refresh token.

        Args:
            data: Session refresh request with refresh token

        Returns:
            OTP verify response with new session and user

        Raises:
            SupabaseAuthError: If session refresh fails
        """
        try:
            session, user = self.repository.refresh_session(data.refresh_token)
        except SupabaseAuthError:
            raise

        return OTPVerifyResponse(
            session=OTPSession(
                access_token=session.get("access_token"),
                refresh_token=session.get("refresh_token"),
                token_type=session.get("token_type", "bearer"),
                expires_in=session.get("expires_in"),
            ),
            user=UserProfile(
                id=user.get("id"),
                phone=user.get("phone"),
            ),
        )
