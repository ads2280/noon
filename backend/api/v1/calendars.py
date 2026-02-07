"""Calendar API routes."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import RedirectResponse

from core.dependencies import AuthenticatedUser, get_current_user, get_user_timezone
from core.timing_logger import log_step, log_start
from domains.calendars.schemas import (
    GoogleAccountResponse,
    GoogleAccountCreate,
    GoogleOAuthStartResponse,
    CalendarResponse,
    CalendarUpdate,
    ScheduleRequest,
    ScheduleResponse,
    CreateEventRequest,
    CreateEventResponse,
    CalendarEvent,
    UpdateEventRequest,
    UpdateEventResponse,
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
    """List all Google accounts for the current user with their calendars."""
    repository = CalendarRepository()
    try:
        account_rows = repository.get_accounts(current_user.id)
        accounts = []
        for account_row in account_rows:
            account_id = account_row["id"]
            # Fetch calendars for this account - include hidden calendars so users can toggle visibility
            calendar_rows = repository.get_calendars_by_account(account_id, include_hidden=True)
            calendars = [CalendarResponse(**cal) for cal in calendar_rows] if calendar_rows else []
            # Create account response with calendars
            account_dict = dict(account_row)
            account_dict["calendars"] = calendars
            accounts.append(GoogleAccountResponse(**account_dict))
    except SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return accounts


@router.post("/accounts/refresh")
async def refresh_calendars(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Refresh calendars from Google API and sync to Supabase.
    
    This endpoint is called by the calendar accounts page to ensure
    calendar metadata is up-to-date. Not needed for agent operations.
    """
    endpoint_start = time.time()
    log_start("backend.api.calendars.refresh_calendars", details=f"user_id={current_user.id}")
    
    service = CalendarService()
    try:
        service_start = time.time()
        await service.hydrate_calendars(current_user.id)
        service_duration = time.time() - service_start
        log_step("backend.api.calendars.refresh_calendars.service", service_duration)
        
        endpoint_duration = time.time() - endpoint_start
        log_step("backend.api.calendars.refresh_calendars", endpoint_duration)
        
        return {"status": "success", "message": "Calendars refreshed successfully"}
    except GoogleCalendarUserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarServiceError as exc:
        logger.exception(
            "GOOGLE_CALENDAR_SERVICE_ERROR user=%s",
            current_user.id,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "UNEXPECTED_ERROR refreshing calendars user=%s",
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(exc)}",
        ) from exc


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
        account = repository.upsert_account(user_id, payload)
        account_id = account["id"]
        repository.sync_calendars(account_id, calendars)
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


@router.put("/{calendar_id}", response_model=CalendarResponse)
async def update_calendar(
    calendar_id: str,
    payload: CalendarUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CalendarResponse:
    """Update a calendar's properties (e.g., is_hidden)."""
    repository = CalendarRepository()
    try:
        updated = repository.update_calendar(
            current_user.id,
            calendar_id,
            payload.model_dump(exclude_none=True),
        )
    except SupabaseStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    
    return CalendarResponse(**updated)


# Calendar operations routes
@router.post("/schedule", response_model=ScheduleResponse)
async def get_schedule(
    payload: ScheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ScheduleResponse:
    """Get schedule for a date range."""
    endpoint_start = time.time()
    log_start("backend.api.calendars.schedule", details=f"user_id={current_user.id} start={payload.start_date} end={payload.end_date}")
    
    # Get user timezone from database
    user_timezone = get_user_timezone(current_user.id)
    
    service = CalendarService()
    try:
        service_start = time.time()
        result = await service.events_for_date_range(
            user_id=current_user.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            timezone_name=user_timezone,
        )
        service_duration = time.time() - service_start
        log_step("backend.api.calendars.schedule.service", service_duration, details=f"event_count={len(result.get('events', []))}")
        
        response_start = time.time()
        response = ScheduleResponse(**result)
        response_duration = time.time() - response_start
        log_step("backend.api.calendars.schedule.build_response", response_duration)
        
        endpoint_duration = time.time() - endpoint_start
        log_step("backend.api.calendars.schedule", endpoint_duration, details=f"event_count={len(result.get('events', []))}")
        return response
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


@router.post("/events", response_model=CreateEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: CreateEventRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CreateEventResponse:
    """Create a new event in Google Calendar."""
    # Get user timezone from database
    user_timezone = get_user_timezone(current_user.id)
    
    service = CalendarService()
    try:
        result = await service.create_event(
            user_id=current_user.id,
            calendar_id=payload.calendar_id,
            summary=payload.summary,
            start=payload.start,
            end=payload.end,
            description=payload.description,
            location=payload.location,
            timezone_name=user_timezone,
        )
        return CreateEventResponse(event=CalendarEvent(**result))
    except GoogleCalendarUserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAPIError as exc:
        if exc.status_code == 403:
            logger.warning(
                "GOOGLE_CALENDAR_INSUFFICIENT_PERMISSIONS user=%s calendar=%s summary=%s",
                current_user.id,
                payload.calendar_id,
                payload.summary,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create events. Please re-link your Google Calendar account with write permissions.",
            ) from exc
        logger.exception(
            "GOOGLE_CALENDAR_API_ERROR user=%s calendar=%s summary=%s",
            current_user.id,
            payload.calendar_id,
            payload.summary,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google Calendar API error: {str(exc)}",
        ) from exc
    except GoogleCalendarServiceError as exc:
        logger.exception(
            "GOOGLE_CALENDAR_SERVICE_ERROR user=%s calendar=%s summary=%s",
            current_user.id,
            payload.calendar_id,
            payload.summary,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    calendar_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    """Delete an event from Google Calendar."""
    service = CalendarService()
    try:
        await service.delete_event(
            user_id=current_user.id,
            calendar_id=calendar_id,
            event_id=event_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except GoogleCalendarUserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAPIError as exc:
        if exc.status_code == 403:
            logger.warning(
                "GOOGLE_CALENDAR_INSUFFICIENT_PERMISSIONS user=%s calendar=%s event=%s",
                current_user.id,
                calendar_id,
                event_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to delete events. Please re-link your Google Calendar account with write permissions.",
            ) from exc
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
    except GoogleCalendarServiceError as exc:
        logger.exception(
            "GOOGLE_CALENDAR_SERVICE_ERROR user=%s calendar=%s event=%s",
            current_user.id,
            calendar_id,
            event_id,
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put("/events/{event_id}", response_model=UpdateEventResponse)
async def update_event(
    event_id: str,
    payload: UpdateEventRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UpdateEventResponse:
    """Update an existing event in Google Calendar."""
    # Get user timezone from database
    user_timezone = get_user_timezone(current_user.id)
    
    service = CalendarService()
    try:
        result = await service.update_event(
            user_id=current_user.id,
            calendar_id=payload.calendar_id,
            event_id=event_id,
            summary=payload.summary,
            start=payload.start,
            end=payload.end,
            description=payload.description,
            location=payload.location,
            timezone_name=user_timezone,
        )
        return UpdateEventResponse(event=CalendarEvent(**result))
    except GoogleCalendarUserError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except GoogleCalendarAPIError as exc:
        if exc.status_code == 403:
            logger.warning(
                "GOOGLE_CALENDAR_INSUFFICIENT_PERMISSIONS user=%s calendar=%s event=%s",
                current_user.id,
                payload.calendar_id,
                event_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update events. Please re-link your Google Calendar account with write permissions.",
            ) from exc
        elif exc.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event not found: {str(exc)}",
            ) from exc
        logger.exception(
            "GOOGLE_CALENDAR_API_ERROR user=%s calendar=%s event=%s",
            current_user.id,
            payload.calendar_id,
            event_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google Calendar API error: {str(exc)}",
        ) from exc
    except GoogleCalendarServiceError as exc:
        logger.exception(
            "GOOGLE_CALENDAR_SERVICE_ERROR user=%s calendar=%s event=%s",
            current_user.id,
            payload.calendar_id,
            event_id,
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
