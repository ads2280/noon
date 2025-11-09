"""Agent router for calendar operations."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from time import perf_counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import AuthenticatedUser, get_current_user
from schemas import agent as agent_schema
from services.calendar_agent import (
    CalendarAgentError,
    CalendarAgentUserError,
    calendar_agent_service,
)

# Ensure noon-agent package is importable for event utilities
agent_path = Path(__file__).parent.parent.parent / "noon-agent"
if str(agent_path) not in sys.path:
    sys.path.insert(0, str(agent_path))

try:
    from noon_agent.db_context import load_user_context_from_db
    from noon_agent.gcal_auth import get_calendar_service
    from noon_agent.gcal_wrapper import get_event_details, read_calendar_events
except ImportError as exc:  # pragma: no cover - startup failure
    logging.error("Failed to import agent modules: %s", exc)
    raise

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=agent_schema.AgentChatResponse)
async def chat_with_agent(
    payload: agent_schema.AgentChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> agent_schema.AgentChatResponse:
    """
    Chat with the calendar agent.

    Accepts natural language input and returns structured JSON with:
    - tool: The action/tool that was called
    - summary: Human-readable summary
    - result: Full tool result (if available)
    - success: Whether the operation succeeded
    """
    truncated_text = payload.text.replace("\n", " ").strip()
    if len(truncated_text) > 160:
        truncated_text = truncated_text[:157] + "…"

    start_time = perf_counter()
    logger.info(
        "AGENT_CHAT_REQUEST user=%s text=%s",
        current_user.id,
        truncated_text,
    )

    try:
        result = calendar_agent_service.chat(
            user_id=current_user.id,
            message=payload.text,
        )
        duration_ms = (perf_counter() - start_time) * 1000
        logger.info(
            "AGENT_CHAT_SUCCESS user=%s tool=%s success=%s duration_ms=%.2f",
            current_user.id,
            result.get("tool"),
            result.get("success"),
            duration_ms,
        )
        return agent_schema.AgentChatResponse(**result)
    except CalendarAgentUserError as exc:
        duration_ms = (perf_counter() - start_time) * 1000
        logger.warning(
            "AGENT_CHAT_USER_ERROR user=%s duration_ms=%.2f error=%s",
            current_user.id,
            duration_ms,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CalendarAgentError as exc:
        duration_ms = (perf_counter() - start_time) * 1000
        logger.exception(
            "AGENT_CHAT_INTERNAL_ERROR user=%s duration_ms=%.2f error=%s",
            current_user.id,
            duration_ms,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/event", response_model=agent_schema.GetEventResponse)
async def get_event_details_with_schedule(
    payload: agent_schema.GetEventRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> agent_schema.GetEventResponse:
    """
    Get full event details by event ID and calendar ID.

    Note: Google Calendar event IDs are unique per calendar, not globally unique.
    Therefore, both event_id and calendar_id are required to uniquely identify an event.

    If calendar_id is not provided, the function will search across all user calendars
    to find the event (less efficient but more convenient).

    Also retrieves the day's schedule for the event's date.

    Returns:
    - event: Full event details
    - day_schedule: All events for that day
    - success: Whether the operation succeeded
    """
    try:
        # Load user context from database
        try:
            user_context = load_user_context_from_db(current_user.id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to load user context: {exc}",
            ) from exc

        # Check if user has Google access token
        access_token = user_context.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has no Google Calendar access token. Please link your Google account first.",
            )

        # Get calendar service
        service = get_calendar_service(access_token)

        # Determine which calendar to search
        calendar_id = payload.calendar_id
        all_calendar_ids = user_context.get("all_calendar_ids", [])

        # If calendar_id not provided, search across all calendars
        if not calendar_id or calendar_id == "primary":
            # Try primary calendar first
            primary_calendar_id = user_context.get("primary_calendar_id", "primary")
            event_result = get_event_details(
                service=service,
                event_id=payload.event_id,
                calendar_id=primary_calendar_id,
            )

            # If not found in primary, search other calendars
            if event_result.get("status") != "success" and all_calendar_ids:
                for cal_id in all_calendar_ids:
                    if cal_id == primary_calendar_id:
                        continue  # Already tried
                    event_result = get_event_details(
                        service=service,
                        event_id=payload.event_id,
                        calendar_id=cal_id,
                    )
                    if event_result.get("status") == "success":
                        calendar_id = cal_id
                        break
        else:
            # Use provided calendar_id
            event_result = get_event_details(
                service=service,
                event_id=payload.event_id,
                calendar_id=calendar_id,
            )

        if event_result.get("status") != "success":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Event not found: "
                    f"{event_result.get('error', 'Unknown error')}. "
                    "Note: Event IDs are unique per calendar, so the event_id must "
                    "exist in the specified calendar_id."
                ),
            )

        event = event_result
        # Update calendar_id in event if we found it in a different calendar
        if calendar_id and event.get("calendar_id") != calendar_id:
            event["calendar_id"] = calendar_id

        # Parse event start time to get the day
        start_time_str = event.get("start", "")
        if not start_time_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event has no start time",
            )

        # Parse the start time to extract the date
        try:
            # Handle both dateTime and date formats
            # Extract just the date part (YYYY-MM-DD)
            if "T" in start_time_str:
                date_part = start_time_str.split("T")[0]
            else:
                date_part = start_time_str

            # Parse date components
            year, month, day = map(int, date_part.split("-")[:3])
            event_start = datetime(year, month, day)
        except (ValueError, IndexError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event start time format: {start_time_str}",
            ) from exc

        # Calculate day boundaries (start and end of the event's day)
        day_start = event_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Get all events for that day (use the calendar_id where we found the event)
        final_calendar_id = event.get("calendar_id", payload.calendar_id or "primary")
        schedule_result = read_calendar_events(
            service=service,
            calendar_id=final_calendar_id,
            time_min=day_start,
            time_max=day_end,
            max_results=500,  # High limit to get all events for the day
        )

        day_schedule = (
            schedule_result
            if schedule_result.get("status") == "success"
            else {
                "status": "error",
                "error": schedule_result.get("error", "Unknown error"),
                "events": [],
                "count": 0,
            }
        )

        return agent_schema.GetEventResponse(
            event=event,
            day_schedule=day_schedule,
            success=True,
        )

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "Error getting event details for user %s: %s",
            current_user.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get event details: {exc}",
        ) from exc
