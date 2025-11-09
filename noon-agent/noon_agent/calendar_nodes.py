"""LangGraph nodes for calendar operations."""

from typing import Any, Dict

from .calendar_state import CalendarAgentState
from .gcal_auth import get_calendar_service
from .tools.context_tools import format_event_list
from .tools.friend_tools import resolve_attendees
from .tools.gcal_tools import (
    check_availability,
    create_event,
    delete_event,
    find_overlap,
    get_schedule,
    search_events,
    update_event,
)


def create_event_node(state: CalendarAgentState) -> Dict[str, Any]:
    """
    Node for creating a calendar event.

    Expected parameters in state["parameters"]:
    - summary: str
    - start_datetime: str (ISO 8601)
    - end_datetime: str (ISO 8601)
    - description: str (optional)
    - attendees: List[str] (optional, can be names or emails)
    """
    service = get_calendar_service(state["user_context"]["access_token"])
    params = state["parameters"] or {}

    # Resolve attendee names to emails if needed
    attendee_names = params.get("attendees", [])
    attendee_emails = []

    if attendee_names:
        resolution = resolve_attendees(
            attendee_names=attendee_names,
            friends=state["user_context"]["friends"],
            threshold=0.7,
        )

        # Check for ambiguous or unresolved
        if resolution["ambiguous"]:
            return {
                **state,
                "needs_clarification": True,
                "clarification_message": f"Multiple matches for: {resolution['ambiguous'][0]['name']}",
                "clarification_options": [
                    m["name"] for m in resolution["ambiguous"][0]["possible_matches"]
                ],
            }

        if resolution["unresolved"]:
            return {
                **state,
                "error": f"Could not find: {resolution['unresolved'][0]['name']}",
            }

        attendee_emails = [r["email"] for r in resolution["resolved"]]

    # Create the event
    result = create_event(
        service=service,
        calendar_id=state["user_context"]["primary_calendar_id"],
        summary=params.get("summary", "New Event"),
        start_datetime=params.get("start_datetime"),
        end_datetime=params.get("end_datetime"),
        description=params.get("description"),
        attendees=attendee_emails if attendee_emails else None,
        timezone=state["user_context"]["timezone"],
    )

    if result["status"] == "success":
        response = f"Created event: {result['details']['summary']} at {result['details']['start']}"
    else:
        response = f"Failed to create event: {result.get('error', 'Unknown error')}"

    return {**state, "result": result, "response": response}


def update_event_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for updating an existing calendar event."""
    service = get_calendar_service(state["user_context"]["access_token"])
    params = state["parameters"] or {}

    result = update_event(
        service=service,
        calendar_id=state["user_context"]["primary_calendar_id"],
        event_id=params.get("event_id"),
        summary=params.get("summary"),
        start_datetime=params.get("start_datetime"),
        end_datetime=params.get("end_datetime"),
        description=params.get("description"),
        attendees=params.get("attendees"),
        timezone=state["user_context"]["timezone"],
    )

    if result["status"] == "success":
        response = f"Updated event: {result['details']['summary']}"
    else:
        response = f"Failed to update event: {result.get('error', 'Unknown error')}"

    return {**state, "result": result, "response": response}


def delete_event_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for deleting a calendar event."""
    service = get_calendar_service(state["user_context"]["access_token"])
    params = state["parameters"] or {}

    result = delete_event(
        service=service,
        calendar_id=state["user_context"]["primary_calendar_id"],
        event_id=params.get("event_id"),
    )

    if result["status"] == "success":
        response = f"Deleted event: {result['details']['deleted_event']['summary']}"
    else:
        response = f"Failed to delete event: {result.get('error', 'Unknown error')}"

    return {**state, "result": result, "response": response}


def search_events_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for searching events across calendars."""
    service = get_calendar_service(state["user_context"]["access_token"])
    params = state["parameters"] or {}

    # Search across all user calendars for overlay view
    result = search_events(
        service=service,
        calendar_ids=state["user_context"]["all_calendar_ids"],
        query=params.get("query", ""),
        time_min=params.get("time_min"),
        time_max=params.get("time_max"),
        max_results_per_calendar=25,
    )

    formatted = format_event_list(result["events"], state["user_context"]["timezone"])
    response = f"Found {result['count']} events:\n{formatted}"

    return {**state, "result": result, "response": response}


def get_schedule_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for getting user's schedule (overlay view of all calendars)."""
    service = get_calendar_service(state["user_context"]["access_token"])
    params = state["parameters"] or {}

    # Get schedule across ALL user calendars
    result = get_schedule(
        service=service,
        calendar_ids=state["user_context"]["all_calendar_ids"],
        time_min=params.get("time_min"),
        time_max=params.get("time_max"),
        timezone=state["user_context"]["timezone"],
    )

    formatted = format_event_list(result["events"], state["user_context"]["timezone"])
    response = (
        f"Your schedule from {params.get('time_min')} to {params.get('time_max')}:\n{formatted}"
    )

    return {**state, "result": result, "response": response}


def check_availability_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for checking user's availability across all calendars."""
    service = get_calendar_service(state["user_context"]["access_token"])
    params = state["parameters"] or {}

    # Check across ALL user calendars to find when they're truly free
    result = check_availability(
        service=service,
        calendar_ids=state["user_context"]["all_calendar_ids"],
        time_min=params.get("time_min"),
        time_max=params.get("time_max"),
        duration_minutes=params.get("duration_minutes", 60),
        timezone=state["user_context"]["timezone"],
    )

    free_count = len(result["free_slots"])
    response = f"Found {free_count} available time slots"

    if free_count > 0:
        # Show first 5 slots
        slots_preview = "\n".join(
            [f"- {slot['start']} to {slot['end']}" for slot in result["free_slots"][:5]]
        )
        response += f":\n{slots_preview}"

    return {**state, "result": result, "response": response}


def find_overlap_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for finding mutual availability across multiple people's calendars."""
    service = get_calendar_service(state["user_context"]["access_token"])
    params = state["parameters"] or {}

    # Resolve friend names to calendar IDs
    friend_names = params.get("friends", [])
    calendar_ids = [state["user_context"]["primary_calendar_id"]]  # Include user's calendar

    if friend_names:
        resolution = resolve_attendees(
            attendee_names=friend_names,
            friends=state["user_context"]["friends"],
            threshold=0.7,
        )

        if resolution["ambiguous"]:
            return {
                **state,
                "needs_clarification": True,
                "clarification_message": f"Multiple matches for: {resolution['ambiguous'][0]['name']}",
                "clarification_options": [
                    m["name"] for m in resolution["ambiguous"][0]["possible_matches"]
                ],
            }

        # Add friend calendar IDs
        calendar_ids.extend([r["calendar_id"] for r in resolution["resolved"]])

    # Find mutual availability
    result = find_overlap(
        service=service,
        calendar_ids=calendar_ids,
        time_min=params.get("time_min"),
        time_max=params.get("time_max"),
        duration_minutes=params.get("duration_minutes", 60),
        timezone=state["user_context"]["timezone"],
    )

    free_count = len(result["common_free_slots"])
    response = f"Found {free_count} time slots when everyone is available"

    if free_count > 0:
        slots_preview = "\n".join(
            [f"- {slot['start']} to {slot['end']}" for slot in result["common_free_slots"][:5]]
        )
        response += f":\n{slots_preview}"

    return {**state, "result": result, "response": response}


def error_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for handling errors."""
    error_msg = state.get("error", "An unknown error occurred")
    return {**state, "response": f"Error: {error_msg}"}


def clarification_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Node for requesting clarification from user."""
    message = state.get("clarification_message", "Need clarification")
    options = state.get("clarification_options", [])

    response = f"{message}\nOptions: {', '.join(options)}"
    return {**state, "response": response}
