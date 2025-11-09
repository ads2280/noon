from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from config import get_settings


class AuthenticatedUser(BaseModel):
    id: str
    phone: Optional[str] = None


def get_current_bearer_token(
    authorization: str = Header(..., alias="Authorization"),
) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    return token


def get_current_user(
    token: str = Depends(get_current_bearer_token),
) -> AuthenticatedUser:
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase JWT secret is not configured on the server.",
        )
    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    return AuthenticatedUser(
        id=user_id, phone=payload.get("phone_number") or payload.get("phone")
    )
