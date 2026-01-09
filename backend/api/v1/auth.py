"""Auth API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from domains.auth.service import AuthService
from domains.auth.schemas import (
    OTPRequest,
    OTPInitResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    SessionRefreshRequest,
)
from utils.errors import SupabaseAuthError, SupabaseStorageError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/otp",
    response_model=OTPInitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_otp(payload: OTPRequest) -> OTPInitResponse:
    """Request OTP to be sent to phone number."""
    service = AuthService()
    try:
        return service.request_otp(payload)
    except SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/verify", response_model=OTPVerifyResponse)
async def verify_otp(payload: OTPVerifyRequest) -> OTPVerifyResponse:
    """Verify OTP code and authenticate user."""
    service = AuthService()
    try:
        return service.verify_otp(payload)
    except SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@router.post("/refresh", response_model=OTPVerifyResponse)
async def refresh_session(payload: SessionRefreshRequest) -> OTPVerifyResponse:
    """Refresh session using refresh token."""
    service = AuthService()
    try:
        return service.refresh_session(payload)
    except SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
