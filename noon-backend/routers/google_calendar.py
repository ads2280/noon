from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from dependencies import AuthenticatedUser, get_current_user
from schemas import google_calendar as schema
from services.google_calendar import (
    GoogleCalendarAuthError,
    GoogleCalendarEventNotFoundError,
    GoogleCalendarServiceError,
    GoogleCalendarUserError,
    google_calendar_service,
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

