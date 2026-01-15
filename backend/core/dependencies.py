from __future__ import annotations

from datetime import datetime
from typing import Annotated

from schemas.user import AuthenticatedUser
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domains.auth.repository import AuthRepository
from utils.errors import SupabaseAuthError, SupabaseStorageError

security = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> AuthenticatedUser:
    """
    Dependency to get the current authenticated user from the request.
    Validates the JWT token and returns the user information.
    Also stores user_id in request.state for middleware access.
    """
    token = credentials.credentials

    repository = AuthRepository()
    try:
        user = await repository.get_user_from_token(token)
    except SupabaseAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except SupabaseStorageError as exc:
        # Check if the storage error is actually an auth error (e.g., JWT expired)
        # This can happen if Supabase returns JWT errors during database queries
        error_msg = str(exc).lower()
        if "jwt" in error_msg or "expired" in error_msg or "unauthorized" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired. Please refresh your session.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        # If it's a real storage error, re-raise as 500
        raise

    if not user or not user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Store user_id in request.state for middleware logging
    request.state.user_id = user["id"]

    return AuthenticatedUser(
        id=user["id"],
        phone=user["phone"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )
