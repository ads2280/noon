"""Calendar API endpoints for the agent.

These endpoints are specifically designed for use by the LangGraph agent
and return data in the format expected by agent tools.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status

from core.dependencies import AuthenticatedUser, get_current_user, get_user_timezone
from domains.calendars.service import CalendarService
from domains.calendars.schemas import ScheduleRequest
from services import agent_calendar_service
from utils.errors import (
    GoogleCalendarUserError,
    GoogleCalendarAuthError,
    GoogleCalendarServiceError,
    GoogleCalendarEventNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/calendars", tags=["agent-calendars"])


def _parse_datetime_or_date(dt_str: str) -> datetime:
    """Parse ISO datetime string, handling both date-only and datetime formats."""
    try:
        # Handle Z suffix and timezone offsets
        normalized = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception as e:
        logger.error(f"Failed to parse datetime: {dt_str} - {e}")
        raise ValueError(f"Invalid datetime format: {dt_str}") from e


@router.get("")
async def list_calendars(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    List calendars from ALL connected Google accounts with write permissions.
    
    Only returns calendars where the user has "writer" or "owner" access role.
    This prevents the agent from selecting read-only calendars for create/update/delete operations.
    
    Returns calendars in format expected by agent tools.
    """
    from domains.calendars.repository import CalendarRepository
    
    try:
        repository = CalendarRepository()
        
        # Get all calendars from repository (these are already synced from all accounts)
        user_calendars = repository.get_calendars(current_user.id)
        
        # Filter to only include calendars with write permissions (writer or owner)
        # This prevents the agent from selecting read-only calendars
        writable_access_roles = {"writer", "owner"}
        
        # Format calendars for agent - only include writable calendars
        formatted_calendars = []
        for cal in user_calendars:
            access_role = cal.get("access_role")
            # Only include calendars with write permissions
            if access_role not in writable_access_roles:
                continue
                
            formatted_calendars.append({
                "id": cal.get("google_calendar_id"),
                "name": cal.get("name"),
                "summary": cal.get("name"),
                "description": cal.get("description"),
                "timezone": "UTC",  # Calendar timezone can vary
                "color": cal.get("color"),
                "is_primary": cal.get("is_primary", False),
                "access_role": access_role,
            })
        
        return {"calendars": formatted_calendars}
        
    except Exception as e:
        # Log full error details for debugging (verbose internal logging)
        logger.error(
            f"Failed to list calendars user_id={current_user.id}: {e}",
            exc_info=True,
        )
        # Return brief, user-friendly message (not technical details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while loading your calendars. Please try again."
        ) from e


@router.post("/schedule")
async def get_schedule(
    payload: Dict[str, Any],
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Read schedule across ALL calendars within a date range.
    
    Expects JSON body with:
    - start_date: ISO date string (e.g., "2026-01-14")
    - end_date: ISO date string (e.g., "2026-01-15")
    
    Returns events from ALL connected Google calendars.
    All events include both id and calendar_id (required for agent tools).
    """
    from datetime import date
    
    try:
        start_date_str = payload.get("start_date")
        end_date_str = payload.get("end_date")
        
        if not start_date_str or not end_date_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date and end_date are required"
            )
        
        # Parse dates
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
        
        # Get user timezone
        user_timezone = get_user_timezone(current_user.id)
        
        # Use CalendarService which aggregates across ALL calendars
        service = CalendarService()
        try:
            result = await service.events_for_date_range(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            timezone_name=user_timezone,
            )
        except Exception as e:
            # Re-raise HTTPExceptions, but wrap other errors
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Error in events_for_date_range: {e}", exc_info=True)
            raise
        
        # Format events for agent tools - ensure both id and calendar_id are present
        formatted_events = []
        for event in result.get("events", []):
            event_id = event.get("id")
            calendar_id = event.get("calendar_id")
            
            if not event_id or not calendar_id:
                logger.warning(f"Event missing required fields (id, calendar_id): {event}")
                continue
            
            formatted_events.append({
                "id": event_id,
                "summary": event.get("summary"),
                "description": event.get("description"),
                "start": event.get("start"),
                "end": event.get("end"),
                "calendar_id": calendar_id,
                "calendar_name": event.get("calendar_name"),
                "location": event.get("raw", {}).get("location"),
                "status": event.get("status"),
            })
        
        return {"events": formatted_events}
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}"
        ) from e
    except GoogleCalendarUserError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except GoogleCalendarAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except GoogleCalendarServiceError as e:
        logger.exception(
            f"Calendar service error user_id={current_user.id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e
    except Exception as e:
        # Log full error details for debugging (verbose internal logging)
        logger.exception(
            f"Unexpected error getting schedule user_id={current_user.id}: {e}",
        )
        # Return brief, user-friendly message (not technical details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while loading your schedule. Please try again."
        ) from e


@router.post("/search")
async def search_events(
    payload: Dict[str, Any],
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Search for events across ALL calendars matching keywords.
    
    Expects JSON body with:
    - keywords: Search query string
    - start_time: ISO datetime string (timezone-aware)
    - end_time: ISO datetime string (timezone-aware)
    
    Returns events from ALL connected Google calendars.
    All events include both id (as event_id) and calendar_id (required for agent tools).
    """
    try:
        keywords = payload.get("keywords", "")
        start_time_str = payload.get("start_time")
        end_time_str = payload.get("end_time")
        
        if not keywords:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="keywords is required"
            )
        
        if not start_time_str or not end_time_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time and end_time are required"
            )
        
        # Parse datetime strings
        start_time = _parse_datetime_or_date(start_time_str)
        end_time = _parse_datetime_or_date(end_time_str)
        
        # Convert to ISO strings for the search function
        # The search_events_for_user expects ISO strings
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()
        
        # Use search_events_for_user which searches across ALL calendars
        result = await agent_calendar_service.search_events_for_user(
            user_id=current_user.id,
            query=keywords,
            time_min=start_iso,
            time_max=end_iso,
        )
        
        # Format events for agent tools - ensure both id and calendar_id are present
        formatted_events = []
        events = result.get("events", [])
        
        for event in events:
            event_id = event.get("event_id") or event.get("id")
            calendar_id = event.get("calendar_id")
            
            if not event_id or not calendar_id:
                logger.warning(f"Event missing required fields (id, calendar_id): {event}")
                continue
            
            formatted_events.append({
                "id": event_id,
                "event_id": event_id,  # Include both for compatibility
                "summary": event.get("summary"),
                "description": event.get("description"),
                "start": event.get("start"),
                "end": event.get("end"),
                "calendar_id": calendar_id,
                "calendar_name": event.get("calendar_name"),
                "location": event.get("location"),
            })
        
        return {"events": formatted_events}
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid datetime format: {str(e)}"
        ) from e
    except Exception as e:
        # Log full error details for debugging (verbose internal logging)
        logger.exception(
            f"Unexpected error searching events user_id={current_user.id}: {e}",
        )
        # Return brief, user-friendly message (not technical details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for events. Please try again."
        ) from e


@router.get("/{calendar_id}/events/{event_id}")
async def get_event(
    calendar_id: str,
    event_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get a single event from a specific calendar.
    
    Returns event details with both id and calendar_id (required for agent tools).
    """
    service = CalendarService()
    
    try:
        # Use CalendarService to get the event
        event = await service.get_event(
            user_id=current_user.id,
            calendar_id=calendar_id,
            event_id=event_id,
        )
        
        # Ensure both id and calendar_id are present (required)
        if "id" not in event:
            event["id"] = event_id
        if "calendar_id" not in event:
            event["calendar_id"] = calendar_id
        
        return event
        
    except GoogleCalendarEventNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    except GoogleCalendarUserError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except GoogleCalendarAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except GoogleCalendarServiceError as e:
        logger.exception(
            f"Calendar service error user_id={current_user.id} calendar={calendar_id} event={event_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        ) from e
    except Exception as e:
        # Log full error details for debugging (verbose internal logging)
        logger.exception(
            f"Unexpected error getting event user_id={current_user.id} calendar={calendar_id} event={event_id}: {e}",
        )
        # Return brief, user-friendly message (not technical details)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while loading the event. Please try again."
        ) from e
