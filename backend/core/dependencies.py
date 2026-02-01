from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from schemas.user import AuthenticatedUser
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domains.auth.repository import AuthRepository
from db.session import get_service_client
from utils.errors import SupabaseAuthError, SupabaseStorageError

security = HTTPBearer()
logger = logging.getLogger(__name__)


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


def get_user_timezone(user_id: str) -> str:
    """
    Get user's timezone from database.
    
    This function fetches the timezone from the Supabase users table and validates it.
    It will error if:
    - The timezone is not found in the database
    - The timezone is empty or None
    - The timezone is "UTC" (considered unconfigured)
    - The timezone is not a valid IANA timezone identifier
    
    Args:
        user_id: User ID
        
    Returns:
        IANA timezone name (e.g., "America/Los_Angeles")
        
    Raises:
        HTTPException: If timezone not found, invalid, or not configured
    """
    supabase_client = get_service_client()
    try:
        user_result = (
            supabase_client.table("users")
            .select("timezone")
            .eq("id", user_id)
            .single()
            .execute()
        )
        
        if not user_result.data:
            logger.error(f"No user data returned user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while retrieving your timezone settings. Please try again."
            )
        
        user_timezone = user_result.data.get("timezone")
        
        # Validate timezone is set and not empty
        if not user_timezone or not user_timezone.strip():
            logger.error(f"User timezone not configured user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User timezone is not configured. Please set your timezone in your account settings."
            )
        
        # Validate timezone is not default 'UTC' (considered unconfigured)
        if user_timezone.upper() == "UTC":
            logger.error(f"User timezone is UTC (unconfigured) user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User timezone is not configured. Please set your timezone in your account settings."
            )
        
        # Validate timezone is a valid IANA timezone
        try:
            ZoneInfo(user_timezone)
        except Exception as e:
            logger.error(
                f"Invalid timezone user_id={user_id} timezone={user_timezone}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid timezone configuration: {user_timezone}. Please set a valid timezone in your account settings."
            ) from e
        
        return user_timezone
        
    except HTTPException:
        # Re-raise HTTPExceptions (our validation errors)
        raise
    except Exception as e:
        logger.error(
            f"Failed to get user timezone user_id={user_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving your timezone settings. Please try again."
        ) from e
