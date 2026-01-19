"""Tool definitions for the calendar scheduling agent."""

import asyncio
import logging
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from agent.calendar_client import create_calendar_client
from agent.schemas.agent_response import (
    ShowScheduleResponse,
    ShowScheduleMetadata,
    ShowEventResponse,
    ShowEventMetadata,
    CreateEventResponse,
    CreateEventMetadata,
    DateTimeDict,
    TimedDateTime,
    AllDayDateTime,
    UpdateEventResponse,
    UpdateEventMetadata,
    DeleteEventResponse,
    DeleteEventMetadata,
    NoActionResponse,
    NoActionMetadata,
)

logger = logging.getLogger(__name__)

# Context variable to store auth for tools (set during tool execution)
import contextvars
_auth_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar('auth', default=None)

def get_auth_context() -> Optional[Dict[str, Any]]:
    """Get auth from context (set during tool execution)."""
    return _auth_context.get()

def set_auth_context(auth: Optional[Dict[str, Any]]):
    """Set auth in context for tool execution."""
    _auth_context.set(auth)

# Global calendar client instance (initialized on module import)
_calendar_client = None

def get_calendar_client():
    """Get or create the global calendar client instance."""
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = create_calendar_client()
    return _calendar_client

def set_calendar_client(client):
    """Set the global calendar client (for testing or custom initialization)."""
    global _calendar_client
    _calendar_client = client


def _run_async(coro):
    """Helper to run async functions synchronously."""
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we're in an async context - this shouldn't happen for tools
            # but handle it by creating a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_async_in_thread, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create new one
        return _run_async_in_thread(coro)

def _run_async_in_thread(coro):
    """Run async function in a new thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Internal tools - gather information without terminating
@tool
def read_schedule(start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """
    Read events from the schedule within a time window.
    
    Args:
        start_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T00:00:00-08:00")
        end_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T23:59:59-08:00")
    
    Returns:
        List of events with minimal details (id, summary, start, end, calendar_id)
        All events include both id and calendar_id (required for event identification).
    """
    try:
        auth = get_auth_context()
        client = get_calendar_client()
        
        # Run async method synchronously
        events = _run_async(
            client.read_schedule(start_time, end_time, auth=auth)
        )
        
        # Log the raw response for debugging
        logger.info(f"read_schedule returned {len(events)} events")
        
        # Ensure all events have both id and calendar_id (required)
        result = []
        for event in events:
            if "id" not in event or "calendar_id" not in event:
                logger.warning(f"Event missing required fields (id, calendar_id): {event}")
                continue
            result.append({
                "id": event["id"],
                "summary": event.get("summary"),
                "start": event.get("start"),
                "end": event.get("end"),
                "calendar_id": event["calendar_id"],
            })
        logger.info(f"read_schedule returning {len(result)} formatted events")
        return result
    except Exception as e:
        logger.error(f"Error in read_schedule: {str(e)}", exc_info=True)
        # Re-raise the error so it's visible in LangSmith traces instead of silently returning empty list
        raise


@tool
def search_events(keywords: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """
    Search for events matching keywords within a time window.
    
    IMPORTANT: Extract key terms from the user's query - don't use full phrases.
    - Remove filler words like "meeting", "with", "my", "the", etc.
    - Extract person names (e.g., "meeting with andrew" → "andrew")
    - Extract event types (e.g., "my haircut appointment" → "haircut")
    
    Args:
        keywords: Key terms to search for (extracted from user query, not literal phrase)
                  Examples: "andrew", "haircut", "jude andrew", "john smith"
                  Bad examples: "meeting with andrew", "my haircut appointment"
        start_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T00:00:00-08:00")
        end_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T23:59:59-08:00")
    
    Returns:
        List of matching events with minimal details.
        All events include both id and calendar_id (required for event identification).
        
    Note: Google Calendar API searches for keywords/phrases in event titles, descriptions, and locations.
          Use extracted key terms, not full natural language phrases.
    """
    try:
        auth = get_auth_context()
        client = get_calendar_client()
        
        # Run async method synchronously
        events = _run_async(
            client.search_events(keywords, start_time, end_time, auth=auth)
        )
        
        # Ensure all events have both id and calendar_id (required)
        result = []
        for event in events:
            if "id" not in event or "calendar_id" not in event:
                logger.warning(f"Event missing required fields (id, calendar_id): {event}")
                continue
            result.append({
                "id": event["id"],
                "summary": event.get("summary"),
                "start": event.get("start"),
                "end": event.get("end"),
                "calendar_id": event["calendar_id"],
            })
        return result
    except Exception as e:
        logger.error(f"Error in search_events: {str(e)}", exc_info=True)
        return []  # Return empty list on error


@tool
def read_event(event_id: str, calendar_id: str) -> Dict[str, Any]:
    """
    Read detailed information about a specific event.
    
    Args:
        event_id: The ID of the event to read
        calendar_id: The ID of the calendar containing the event
    
    Returns:
        Detailed event information with both id and calendar_id (required).
    """
    try:
        auth = get_auth_context()
        client = get_calendar_client()
        
        # Run async method synchronously
        event = _run_async(
            client.read_event(event_id, calendar_id, auth=auth)
        )
        
        # Ensure both id and calendar_id are present (required)
        if "id" not in event:
            event["id"] = event_id
        if "calendar_id" not in event:
            event["calendar_id"] = calendar_id
            
        return event
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in read_event: {error_msg}", exc_info=True)
        # Return actionable error message
        is_404 = "404" in error_msg.lower() or "not found" in error_msg.lower()
        if is_404:
            actionable_error = f"ERROR: Event {event_id} not found in calendar {calendar_id}. This likely means the event_id and calendar_id don't match (they may have come from different events in the search results). You should search_events again and ensure you extract BOTH event_id AND calendar_id from the SAME event that matches the user's description."
        else:
            actionable_error = f"ERROR: Failed to read event {event_id} from calendar {calendar_id}: {error_msg}"
        return {
            "id": event_id,
            "calendar_id": calendar_id,
            "error": actionable_error,
        }


@tool
def list_calendars() -> List[Dict[str, Any]]:
    """
    List all available calendars from ALL connected Google accounts with write permissions.
    
    IMPORTANT: This tool returns ONLY calendars where you have write access (access_role: "writer" or "owner").
    Use this tool to get valid calendar_ids for create/update/delete operations.
    
    Returns:
        List of calendars with their details, including:
        - id: Calendar ID (use this for calendar_id in create/update/delete operations)
        - name: Calendar name
        - access_role: Permission level ("writer" or "owner" - both allow write operations)
        - is_primary: Whether this is the user's primary calendar (prefer this if available)
    """
    try:
        auth = get_auth_context()
        client = get_calendar_client()
        
        # Run async method synchronously
        calendars = _run_async(
            client.list_calendars(auth=auth)
        )
        
        return calendars
    except Exception as e:
        logger.error(f"Error in list_calendars: {str(e)}", exc_info=True)
        return []  # Return empty list on error


# External tools - terminate agent and return response
@tool
def show_schedule(start_time: str, end_time: str) -> Dict[str, Any]:
    """
    Show the schedule to the user. This terminates the agent.
    
    Args:
        start_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T00:00:00-08:00")
        end_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T23:59:59-08:00")
    
    Returns:
        Dict with type "show-schedule" and metadata
    """
    # Parse datetime strings to datetime objects
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)
    
    response = ShowScheduleResponse(
        metadata=ShowScheduleMetadata(
            start_date=start_dt,
            end_date=end_dt,
        )
    )
    return response.model_dump()


@tool
def show_event(event_id: str, calendar_id: str) -> Dict[str, Any]:
    """
    Show a specific event to the user. This terminates the agent.
    
    Args:
        event_id: The ID of the event to show
        calendar_id: The ID of the calendar containing the event
    
    Returns:
        Dict with type "show-event" and metadata
    """
    response = ShowEventResponse(
        metadata=ShowEventMetadata(
            event_id=event_id,
            calendar_id=calendar_id,
        )
    )
    return response.model_dump()


@tool
def request_create_event(
    summary: str,
    calendar_id: str,
    start_time: str = None,
    end_time: str = None,
    start_date: str = None,
    end_date: str = None,
    description: str = None,
    location: str = None,
) -> Dict[str, Any]:
    """
    Request to create a new event. This terminates the agent.
    
    IMPORTANT: Only include description if:
    - The user explicitly requests a description in their query
    - The description is necessary for clarity (e.g., meeting agenda, important notes)
    - Do NOT add descriptions automatically or make them up
    
    Args:
        summary: Title/summary of the event
        calendar_id: ID of the calendar to create the event on
        start_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T10:00:00-08:00")
                   Required for timed events. Mutually exclusive with start_date.
        end_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T11:00:00-08:00")
                 Required for timed events. Mutually exclusive with end_date.
        start_date: Date string in "YYYY-MM-DD" format (e.g., "2026-01-14")
                   Required for all-day events. Mutually exclusive with start_time.
        end_date: Date string in "YYYY-MM-DD" format (e.g., "2026-01-15")
                 Required for all-day events. Mutually exclusive with end_time.
                 Note: End date is exclusive (represents the day after the event ends).
        description: Optional description of the event. Only include if explicitly requested or necessary.
        location: Optional location for the event
    
    Returns:
        Dict with type "create-event" and metadata
    """
    # Validate that either datetime or date is provided (not both, not neither)
    has_datetime = start_time is not None and end_time is not None
    has_date = start_date is not None and end_date is not None
    
    if not has_datetime and not has_date:
        raise ValueError("Either (start_time, end_time) or (start_date, end_date) must be provided")
    if has_datetime and has_date:
        raise ValueError("Cannot provide both datetime and date fields. Use datetime for timed events, date for all-day events.")
    
    if has_date:
        # Parse date strings to date objects for all-day events
        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)
        
        metadata = CreateEventMetadata(
            summary=summary,
            start=AllDayDateTime(date=start_d),
            end=AllDayDateTime(date=end_d),
            calendar_id=calendar_id,
            description=description,
            location=location,
        )
    else:
        # Parse datetime strings to datetime objects for timed events
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        
        metadata = CreateEventMetadata(
            summary=summary,
            start=TimedDateTime(dateTime=start_dt),
            end=TimedDateTime(dateTime=end_dt),
            calendar_id=calendar_id,
            description=description,
            location=location,
        )
    
    response = CreateEventResponse(metadata=metadata)
    return response.model_dump()


@tool
def request_update_event(
    event_id: str,
    calendar_id: str,
    summary: str = None,
    start_time: str = None,
    end_time: str = None,
    start_date: str = None,
    end_date: str = None,
    description: str = None,
    location: str = None,
) -> Dict[str, Any]:
    """
    Request to update an existing event. This terminates the agent.
    
    IMPORTANT: Only include description if:
    - The user explicitly requests to update or add a description
    - The description change is necessary for clarity
    - Do NOT add or modify descriptions automatically or make them up
    
    Args:
        event_id: The ID of the event to update
        calendar_id: The ID of the calendar containing the event
        summary: Optional new summary/title
        start_time: Optional new start time (timezone-aware ISO format datetime string with offset, e.g., "2026-01-14T10:00:00-08:00")
                   For timed events. Mutually exclusive with start_date.
        end_time: Optional new end time (timezone-aware ISO format datetime string with offset, e.g., "2026-01-14T11:00:00-08:00")
                 For timed events. Mutually exclusive with end_date.
        start_date: Optional new start date (date string in "YYYY-MM-DD" format, e.g., "2026-01-14")
                   For all-day events. Mutually exclusive with start_time.
        end_date: Optional new end date (date string in "YYYY-MM-DD" format, e.g., "2026-01-15")
                 For all-day events. Mutually exclusive with end_time.
                 Note: End date is exclusive (represents the day after the event ends).
        description: Optional new description. Only include if explicitly requested or necessary.
        location: Optional new location
    
    Returns:
        Dict with type "update-event" and metadata
    """
    # Validate that datetime and date are not mixed
    has_datetime = start_time is not None or end_time is not None
    has_date = start_date is not None or end_date is not None
    
    if has_datetime and has_date:
        raise ValueError("Cannot provide both datetime and date fields. Use datetime for timed events, date for all-day events.")
    
    # Parse and create DateTimeDict union objects
    start_dt = None
    end_dt = None
    
    if has_date:
        # Handle all-day events
        if start_date:
            start_dt = AllDayDateTime(date=date.fromisoformat(start_date))
        if end_date:
            end_dt = AllDayDateTime(date=date.fromisoformat(end_date))
    elif has_datetime:
        # Handle timed events
        if start_time:
            start_dt = TimedDateTime(dateTime=datetime.fromisoformat(start_time))
        if end_time:
            end_dt = TimedDateTime(dateTime=datetime.fromisoformat(end_time))
    
    metadata = UpdateEventMetadata(
        event_id=event_id,
        calendar_id=calendar_id,
        summary=summary,
        start=start_dt,
        end=end_dt,
        description=description,
        location=location,
    )
    
    response = UpdateEventResponse(metadata=metadata)
    return response.model_dump()


@tool
def request_delete_event(event_id: str, calendar_id: str) -> Dict[str, Any]:
    """
    Request to delete an event. This terminates the agent.
    
    Args:
        event_id: The ID of the event to delete
        calendar_id: The ID of the calendar containing the event
    
    Returns:
        Dict with type "delete-event" and metadata
    """
    response = DeleteEventResponse(
        metadata=DeleteEventMetadata(
            event_id=event_id,
            calendar_id=calendar_id,
        )
    )
    return response.model_dump()


@tool
def do_nothing(reason: str) -> Dict[str, Any]:
    """
    Do nothing and terminate the agent. Use this when the request cannot be fulfilled
    or is not supported.
    
    Args:
        reason: Explanation of why no action is being taken
    
    Returns:
        Dict with type "no-action" and metadata
    """
    response = NoActionResponse(
        metadata=NoActionMetadata(reason=reason)
    )
    return response.model_dump()


# Lists of tools for easy access
INTERNAL_TOOLS = [read_schedule, search_events, read_event, list_calendars]
EXTERNAL_TOOLS = [
    show_schedule,
    show_event,
    request_create_event,
    request_update_event,
    request_delete_event,
    do_nothing,
]
ALL_TOOLS = INTERNAL_TOOLS + EXTERNAL_TOOLS
