"""Tool definitions for the calendar scheduling agent."""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from agent.calendar_client import create_calendar_client

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
    
    Args:
        keywords: Space-separated keywords to search for
        start_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T00:00:00-08:00")
        end_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T23:59:59-08:00")
    
    Returns:
        List of matching events with minimal details.
        All events include both id and calendar_id (required for event identification).
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
        logger.error(f"Error in read_event: {str(e)}", exc_info=True)
        # Return minimal event dict on error
        return {
            "id": event_id,
            "calendar_id": calendar_id,
            "error": str(e),
        }


@tool
def list_calendars() -> List[Dict[str, Any]]:
    """
    List all available calendars from ALL connected Google accounts.
    
    Returns:
        List of calendars with their details
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
    return {
        "type": "show-schedule",
        "metadata": {
            "start-date": start_time,
            "end-date": end_time,
        },
    }


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
    return {
        "type": "show-event",
        "metadata": {
            "event-id": event_id,
            "calendar-id": calendar_id,
        },
    }


@tool
def request_create_event(
    summary: str,
    start_time: str,
    end_time: str,
    calendar_id: str,
    description: str = None,
    location: str = None,
) -> Dict[str, Any]:
    """
    Request to create a new event. This terminates the agent.
    
    Args:
        summary: Title/summary of the event
        start_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T10:00:00-08:00")
        end_time: Timezone-aware ISO format datetime string with offset (e.g., "2026-01-14T11:00:00-08:00")
        calendar_id: ID of the calendar to create the event on
        description: Optional description of the event
        location: Optional location for the event
    
    Returns:
        Dict with type "create-event" and metadata
    """
    metadata = {
        "summary": summary,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
        "calendar_id": calendar_id,
    }
    
    if description:
        metadata["description"] = description
    if location:
        metadata["location"] = location
    
    return {
        "type": "create-event",
        "metadata": metadata,
    }


@tool
def request_update_event(
    event_id: str,
    calendar_id: str,
    summary: str = None,
    start_time: str = None,
    end_time: str = None,
    description: str = None,
    location: str = None,
) -> Dict[str, Any]:
    """
    Request to update an existing event. This terminates the agent.
    
    Args:
        event_id: The ID of the event to update
        calendar_id: The ID of the calendar containing the event
        summary: Optional new summary/title
        start_time: Optional new start time (timezone-aware ISO format datetime string with offset, e.g., "2026-01-14T10:00:00-08:00")
        end_time: Optional new end time (timezone-aware ISO format datetime string with offset, e.g., "2026-01-14T11:00:00-08:00")
        description: Optional new description
        location: Optional new location
    
    Returns:
        Dict with type "update-event" and metadata
    """
    metadata = {
        "event-id": event_id,
        "calendar-id": calendar_id,
    }
    
    if summary:
        metadata["summary"] = summary
    if start_time:
        metadata["start"] = {"dateTime": start_time}
    if end_time:
        metadata["end"] = {"dateTime": end_time}
    if description:
        metadata["description"] = description
    if location:
        metadata["location"] = location
    
    return {
        "type": "update-event",
        "metadata": metadata,
    }


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
    return {
        "type": "delete-event",
        "metadata": {
            "event-id": event_id,
            "calendar-id": calendar_id,
        },
    }


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
    return {
        "type": "no-action",
        "metadata": {
            "reason": reason,
        },
    }


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
