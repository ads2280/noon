from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from schemas import auth as auth_schema
from services import supabase_client

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/otp",
    response_model=auth_schema.OTPInitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_otp(payload: auth_schema.OTPRequest) -> auth_schema.OTPInitResponse:
    try:
        supabase_client.send_phone_otp(payload.phone)
    except supabase_client.SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return auth_schema.OTPInitResponse()


@router.post("/verify", response_model=auth_schema.OTPVerifyResponse)
async def verify_otp(
    payload: auth_schema.OTPVerifyRequest,
) -> auth_schema.OTPVerifyResponse:
    try:
        session, user = supabase_client.verify_phone_otp(payload.phone, payload.code)
    except supabase_client.SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        supabase_client.ensure_user_profile(user, payload.phone)
    except supabase_client.SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return auth_schema.OTPVerifyResponse(
        session=auth_schema.OTPSession(
            access_token=session.get("access_token"),
            refresh_token=session.get("refresh_token"),
            token_type=session.get("token_type", "bearer"),
            expires_in=session.get("expires_in"),
        ),
        user=auth_schema.UserProfile(id=user.get("id"), phone=user.get("phone")),
    )
