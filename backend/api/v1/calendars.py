"""Calendar API routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from core.dependencies import AuthenticatedUser, get_current_user
from domains.calendars.schemas import (
    GoogleAccountResponse,
    GoogleAccountCreate,
    GoogleOAuthStartResponse,
    EventSurroundingScheduleRequest,
    EventSurroundingScheduleResponse,
    ScheduleRequest,
    ScheduleResponse,
)
from domains.calendars.service import CalendarService
from domains.calendars.repository import CalendarRepository
from domains.calendars.providers.google import (
    create_state_token,
    decode_state_token,
    build_authorization_url,
    exchange_code_for_tokens,
    fetch_profile,
    fetch_calendar_list,
    build_app_redirect_url,
    GoogleCalendarProvider,
)
from utils.errors import (
    SupabaseStorageError,
    GoogleStateError,
    GoogleOAuthError,
    GoogleCalendarEventNotFoundError,
    GoogleCalendarUserError,
    GoogleCalendarAuthError,
    GoogleCalendarServiceError,
    GoogleCalendarAPIError,
)

router = APIRouter(prefix="/calendars", tags=["calendars"])
logger = logging.getLogger(__name__)


# Account management routes
@router.get("/accounts", response_model=list[GoogleAccountResponse])
async def list_accounts(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[GoogleAccountResponse]:
    """List all Google accounts for the current user."""
    repository = CalendarRepository()
    try:
        rows = repository.get_accounts(current_user.id)
    except SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return [GoogleAccountResponse(**row) for row in rows]


@router.post("/accounts/oauth/start", response_model=GoogleOAuthStartResponse)
async def start_oauth(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> GoogleOAuthStartResponse:
    """Start Google OAuth flow."""
    state = create_state_token(current_user.id)
    try:
        claims = decode_state_token(state)
    except GoogleStateError:
        # This should never happen because we issue the token, but guard regardless.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare OAuth state token.",
        )

    authorization_url = build_authorization_url(state)
    expires_at = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
    return GoogleOAuthStartResponse(
        authorization_url=authorization_url,
        state=state,
        state_expires_at=expires_at,
    )


@router.get("/accounts/oauth/callback", include_in_schema=False)
async def oauth_callback(state: str, code: str) -> RedirectResponse:
    """Handle Google OAuth callback."""
    try:
        claims = decode_state_token(state)
    except GoogleStateError as exc:
        logger.warning("Rejected Google OAuth callback with invalid state: %s", exc)
        redirect_url = build_app_redirect_url(
            False, state="", message="invalid_state"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    user_id = claims.get("sub")
    if not user_id:
        redirect_url = build_app_redirect_url(
            False, state, message="missing_user"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    try:
        tokens = await exchange_code_for_tokens(code)
        profile = await fetch_profile(tokens.access_token)
        calendars = await fetch_calendar_list(tokens.access_token)
    except GoogleOAuthError as exc:
        logger.error("Google OAuth flow failed for user %s: %s", user_id, exc)
        redirect_url = build_app_redirect_url(
            False, state, message="google_error"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    except Exception:  # pragma: no cover - unexpected runtime issues
        logger.exception(
            "Unexpected error during Google OAuth callback for user %s", user_id
        )
        redirect_url = build_app_redirect_url(
            False, state, message="unexpected_error"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    expires_at = tokens.expires_at()
    metadata: dict[str, object] = {
        "scopes": tokens.scopes,
        "calendars": calendars,
        "linked_at": datetime.now(timezone.utc).isoformat(),
        "token_type": tokens.token_type,
    }
    if tokens.id_token:
        metadata["id_token"] = tokens.id_token

    payload = {
        "google_user_id": profile.id,
        "email": profile.email,
        "display_name": profile.name,
        "avatar_url": profile.picture,
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "metadata": metadata,
    }

    repository = CalendarRepository()
    try:
        repository.upsert_account(user_id, payload)
        repository.sync_calendars(user_id, calendars)
    except SupabaseStorageError as exc:
        logger.error("Failed to persist Google account for user %s: %s", user_id, exc)
        redirect_url = build_app_redirect_url(
            False, state, message="storage_error"
        )
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    redirect_url = build_app_redirect_url(True, state, message="linked")
    return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/accounts",
    response_model=GoogleAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    payload: GoogleAccountCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> GoogleAccountResponse:
    """Create a Google account."""
    repository = CalendarRepository()
    try:
        row = repository.upsert_account(
            current_user.id, payload.model_dump(exclude_none=True)
        )
    except SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return GoogleAccountResponse(**row)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """Delete a Google account."""
    repository = CalendarRepository()
    try:
        repository.delete_account(current_user.id, account_id)
    except SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Calendar operations routes
@router.post(
    "/event-surrounding-schedule",
    response_model=EventSurroundingScheduleResponse,
)
async def get_event_surrounding_schedule(
    payload: EventSurroundingScheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> EventSurroundingScheduleResponse:
    """Get event and surrounding schedule."""
    service = CalendarService()
    try:
        result = await service.events_for_event_window(
            user_id=current_user.id,
            event_id=payload.event_id,
            calendar_id=payload.calendar_id,
            timezone_name=payload.timezone,
        )
        return EventSurroundingScheduleResponse(**result)
    except GoogleCalendarEventNotFoundError as exc:
        logger.info(
            "GOOGLE_CALENDAR_EVENT_NOT_FOUND user=%s event=%s calendar=%s",
            current_user.id,
            payload.event_id,
            payload.calendar_id,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarUserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarServiceError as exc:
        logger.exception(
            "GOOGLE_CALENDAR_SERVICE_ERROR user=%s event=%s calendar=%s",
            current_user.id,
            payload.event_id,
            payload.calendar_id,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/schedule", response_model=ScheduleResponse)
async def get_schedule(
    payload: ScheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ScheduleResponse:
    """Get schedule for a date range."""
    service = CalendarService()
    try:
        result = await service.events_for_date_range(
            user_id=current_user.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            timezone_name=payload.timezone,
        )
        return ScheduleResponse(**result)
    except GoogleCalendarUserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarServiceError as exc:
        logger.exception(
            "GOOGLE_CALENDAR_SERVICE_ERROR user=%s start=%s end=%s",
            current_user.id,
            payload.start_date,
            payload.end_date,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/calendar/{calendar_id}/event/{event_id}")
async def get_event(
    calendar_id: str,
    event_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a single event from a Google Calendar."""
    service = CalendarService()
    repository = CalendarRepository()
    try:
        # Get the user's Google accounts
        accounts = repository.get_accounts(current_user.id)
        if not accounts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No Google account linked. Please link a Google account first.",
            )

        # Use the first account (you may want to allow selecting which account to use)
        account = accounts[0]
        access_token = account.get("access_token")
        refresh_token = account.get("refresh_token")

        if not access_token or not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google account missing access or refresh token.",
            )

        # Create provider and get event
        provider = GoogleCalendarProvider(
            access_token=access_token,
            refresh_token=refresh_token,
        )
        event = await provider.get_event(
            calendar_id=calendar_id,
            event_id=event_id,
        )

        return event

    except GoogleCalendarAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event not found: {str(exc)}",
            ) from exc
        elif exc.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google authentication failed. Please re-link your Google account.",
            ) from exc
        elif exc.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this calendar or event.",
            ) from exc
        else:
            logger.exception(
                "GOOGLE_CALENDAR_API_ERROR user=%s calendar=%s event=%s",
                current_user.id,
                calendar_id,
                event_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Google Calendar API error: {str(exc)}",
            ) from exc
    except SupabaseStorageError as exc:
        logger.exception(
            "SUPABASE_ERROR user=%s calendar=%s event=%s",
            current_user.id,
            calendar_id,
            event_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.exception(
            "UNEXPECTED_ERROR user=%s calendar=%s event=%s",
            current_user.id,
            calendar_id,
            event_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(exc)}",
        ) from exc
