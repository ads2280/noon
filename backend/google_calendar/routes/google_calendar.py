from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import AuthenticatedUser, get_current_user
from schemas import google_calendar as schema
from services import supabase_client
from google_calendar.utils.google_calendar import (
    GoogleCalendarAuthError,
    GoogleCalendarEventNotFoundError,
    GoogleCalendarServiceError,
    GoogleCalendarUserError,
    google_calendar_service,
)
from google_calendar.utils.calendar_wrapper import (
    GoogleCalendarAPIError,
    GoogleCalendarCredentials,
    GoogleCalendarWrapper,
)

router = APIRouter(prefix="/google-calendar", tags=["google_calendar"])
logger = logging.getLogger(__name__)


@router.post(
    "/event-surrounding-schedule",
    response_model=schema.EventSurroundingScheduleResponse,
)
async def get_event_surrounding_schedule(
    payload: schema.EventSurroundingScheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> schema.EventSurroundingScheduleResponse:
    try:
        result = await google_calendar_service.events_for_event_window(
            user_id=current_user.id,
            event_id=payload.event_id,
            calendar_id=payload.calendar_id,
            timezone_name=payload.timezone,
        )
        return schema.EventSurroundingScheduleResponse(**result)
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


@router.post("/schedule", response_model=schema.ScheduleResponse)
async def get_schedule(
    payload: schema.ScheduleRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> schema.ScheduleResponse:
    try:
        result = await google_calendar_service.events_for_date_range(
            user_id=current_user.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            timezone_name=payload.timezone,
        )
        return schema.ScheduleResponse(**result)
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
    """
    Get a single event from a Google Calendar.

    Uses the calendar wrapper service with OAuth credentials from the user's Google account.
    """
    try:
        # Get the user's Google accounts
        accounts = supabase_client.list_google_accounts(current_user.id)
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

        # Create credentials and wrapper
        credentials = GoogleCalendarCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
        )
        wrapper = GoogleCalendarWrapper(credentials)

        # Get the event
        event = await wrapper.get_event(
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
    except supabase_client.SupabaseStorageError as exc:
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
