from __future__ import annotations

from datetime import datetime
from typing import Annotated

from schemas.user import AuthenticatedUser
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services import supabase_client

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> AuthenticatedUser:
    """
    Dependency to get the current authenticated user from the request.
    Validates the JWT token and returns the user information.
    """
    token = credentials.credentials

    try:
        user = await supabase_client.get_user_from_token(token)
    except supabase_client.SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not user or not user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        id=user["id"],
        phone=user["phone"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )
