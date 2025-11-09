from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class OTPRequest(BaseModel):
    phone: str = Field(..., min_length=6, max_length=20, pattern=r"^\+?[1-9]\d{5,19}$")


class OTPInitResponse(BaseModel):
    status: str = "otp_sent"


class OTPVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=6, max_length=20, pattern=r"^\+?[1-9]\d{5,19}$")
    code: str = Field(..., min_length=4, max_length=10, pattern=r"^\d+$")


class UserProfile(BaseModel):
    id: str
    phone: Optional[str] = None


class OTPSession(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None


class OTPVerifyResponse(BaseModel):
    session: OTPSession
    user: UserProfile


class SessionRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10, max_length=1024)
