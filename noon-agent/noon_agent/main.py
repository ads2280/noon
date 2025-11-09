"""Noon agent - Simple Google Calendar operations with LangGraph."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.runnables import Runnable

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from .helpers import build_intent_parser
from .gcal_wrapper import (
    get_calendar_service,
    create_calendar_event,
    delete_calendar_event,
    update_calendar_event,
    search_calendar_events,
)
from .constants import self


class State(TypedDict, total=False):
    """Internal state propagated between graph nodes."""

    messages: str | List[Dict[str, Any]]
    context: Dict[str, Any]
    action: Literal["create", "delete", "update", "read"]
    start_time: datetime | None
    end_time: datetime | None
    location: str | None
    people: List[str] | None
    name: str | None
    auth_provider: str | None
    auth_token: str | None
    summary: str
    response: str
    success: bool


class OutputState(TypedDict):
    response: str
    success: bool


def route_action(state: State) -> str:
    """Select the next node based on requested action; default to read."""
    action = state.get("action", "read")
    logger.info(f"ROUTE_ACTION: Routing to action: {action}")
    return action


def get_intent_chain() -> Runnable:
    return build_intent_parser()


def parse_intent(state: State) -> State:
    """Call the LLM to normalize the user's scheduling intent."""
    logger.info("=" * 80)
    logger.info("PARSE_INTENT: Starting intent parsing")

    raw_messages = state.get("messages") or ""
    if isinstance(raw_messages, str):
        logger.info(f"PARSE_INTENT: User message: {raw_messages}")
        normalized_messages: List[Dict[str, Any]] = [{"role": "human", "content": raw_messages}]
    else:
        normalized_messages = raw_messages

    logger.info("PARSE_INTENT: Calling LLM to extract structured intent...")
    parsed = get_intent_chain().invoke({"messages": normalized_messages})
    next_state = dict(state)
    next_state.update(parsed.model_dump())

    logger.info(f"PARSE_INTENT: Parsed intent - action={next_state.get('action')}")
    logger.info(f"PARSE_INTENT: Parsed intent - name={next_state.get('name')}")
    logger.info(f"PARSE_INTENT: Parsed intent - summary={next_state.get('summary')}")
    logger.info(f"PARSE_INTENT: Parsed intent - start_time={next_state.get('start_time')}")
    logger.info(f"PARSE_INTENT: Parsed intent - end_time={next_state.get('end_time')}")
    logger.info(f"PARSE_INTENT: Parsed intent - people={next_state.get('people')}")
    logger.info(f"PARSE_INTENT: Parsed intent - location={next_state.get('location')}")

    # Ensure self user is always included in people list for create/update actions
    if next_state.get("action") in ["create", "update"]:
        self_email = list(self.values())[0] if self else None
        if self_email:
            people = next_state.get("people") or []
            if self_email not in people:
                logger.info(f"PARSE_INTENT: Adding self user {self_email} to people list")
                people.append(self_email)
            next_state["people"] = people
            logger.info(f"PARSE_INTENT: Final people list: {next_state['people']}")

    logger.info("PARSE_INTENT: Intent parsing complete")
    logger.info("=" * 80)
    return next_state


def _with_summary(state: State, message: str) -> State:
    next_state = dict(state)
    next_state["summary"] = message
    return next_state


def summarize_result(state: State) -> OutputState:
    """Return a user-facing description of what the graph just did."""

    summary = state.get("summary") or "No additional details were provided."
    action = state.get("action", "read")
    result = f"{action.capitalize()} action completed: {summary}"
    return {"response": result, "success": True}


def create_event(state: State) -> State:
    """Create a calendar event using Google Calendar API."""
    logger.info("=" * 80)
    logger.info("CREATE_EVENT: Starting event creation")
    try:
        logger.info("CREATE_EVENT: Getting Google Calendar service...")
        service = get_calendar_service()

        # Handle event title - try name first, then summary, then default
        event_title = state.get("name") or state.get("summary") or "New Event"
        logger.info(f"CREATE_EVENT: Event title: {event_title}")

        # Validate required fields
        start_time = state.get("start_time")
        end_time = state.get("end_time")
        logger.info(f"CREATE_EVENT: Start time: {start_time}")
        logger.info(f"CREATE_EVENT: End time: {end_time}")

        if not start_time or not end_time:
            debug_info = f"start_time={start_time}, end_time={end_time}"
            logger.error(f"CREATE_EVENT: Missing required time fields - {debug_info}")
            return _with_summary(
                state,
                f"Failed to create event: start_time and end_time are required. Parsed: {debug_info}",
            )

        attendees = state.get("people")
        logger.info(f"CREATE_EVENT: Attendees: {attendees}")
        logger.info(
            f"CREATE_EVENT: Description: {state.get('summary') if state.get('name') else None}"
        )

        logger.info("CREATE_EVENT: Calling Google Calendar API...")
        result = create_calendar_event(
            service=service,
            summary=event_title,
            start_time=start_time,
            end_time=end_time,
            description=state.get("summary") if state.get("name") else None,
            attendees=attendees,
        )

        if result["status"] == "success":
            message = f"Created event: {result['summary']} at {result['start']}"
            logger.info(f"CREATE_EVENT: SUCCESS - {message}")
            logger.info(f"CREATE_EVENT: Event ID: {result['event_id']}")
            logger.info(f"CREATE_EVENT: Event link: {result.get('link')}")
        else:
            message = f"Failed to create event: {result.get('error', 'Unknown error')}"
            logger.error(f"CREATE_EVENT: FAILED - {message}")

        logger.info("=" * 80)
        return _with_summary(state, message)
    except Exception as e:
        logger.exception(f"CREATE_EVENT: EXCEPTION - {str(e)}")
        logger.info("=" * 80)
        return _with_summary(state, f"Error creating event: {str(e)}")


def read_event(state: State) -> State:
    """Read/list calendar events using Google Calendar API."""
    logger.info("=" * 80)
    logger.info("READ_EVENT: Starting event read")
    try:
        logger.info("READ_EVENT: Getting Google Calendar service...")
        service = get_calendar_service()

        logger.info(
            f"READ_EVENT: Time range - start: {state.get('start_time')}, end: {state.get('end_time')}"
        )
        result = read_calendar_events(
            service=service,
            time_min=state.get("start_time"),
            time_max=state.get("end_time"),
        )

        if result["status"] == "success":
            logger.info(f"READ_EVENT: Found {result['count']} events")
            event_list = "\n".join([f"- {e['summary']} at {e['start']}" for e in result["events"]])
            message = (
                f"Found {result['count']} events:\n{event_list}"
                if result["count"] > 0
                else "No events found."
            )
        else:
            message = f"Failed to read events: {result.get('error', 'Unknown error')}"
            logger.error(f"READ_EVENT: FAILED - {message}")

        logger.info("=" * 80)
        return _with_summary(state, message)
    except Exception as e:
        logger.exception(f"READ_EVENT: EXCEPTION - {str(e)}")
        logger.info("=" * 80)
        return _with_summary(state, f"Error reading events: {str(e)}")


def update_event(state: State) -> State:
    """Update a calendar event using Google Calendar API."""
    try:
        service = get_calendar_service()

        result = update_calendar_event(
            service=service,
            event_id=state.get("event_id"),
            summary=state.get("summary"),
            start_time=state.get("start_time"),
            end_time=state.get("end_time"),
            description=state.get("description"),
        )

        if result["status"] == "success":
            message = f"Updated event: {result['summary']}"
        else:
            message = f"Failed to update event: {result.get('error', 'Unknown error')}"

        return _with_summary(state, message)
    except Exception as e:
        return _with_summary(state, f"Error updating event: {str(e)}")


def delete_event(state: State) -> State:
    """Delete a calendar event using Google Calendar API."""
    try:
        service = get_calendar_service()

        result = delete_calendar_event(
            service=service,
            event_id=state.get("event_id"),
        )

        if result["status"] == "success":
            message = result["message"]
        else:
            message = f"Failed to delete event: {result.get('error', 'Unknown error')}"

        return _with_summary(state, message)
    except Exception as e:
        return _with_summary(state, f"Error deleting event: {str(e)}")


def search_event(state: State) -> State:
    """Search calendar events using free text query."""
    try:
        service = get_calendar_service()

        result = search_calendar_events(
            service=service,
            query=state.get("query", ""),
            time_min=state.get("start_time"),
            time_max=state.get("end_time"),
        )

        if result["status"] == "success":
            if result["count"] > 0:
                event_list = "\n".join(
                    [f"- {e['summary']} at {e['start']}" for e in result["events"]]
                )
                message = (
                    f"Found {result['count']} events matching '{state.get('query')}':\n{event_list}"
                )
            else:
                message = f"No events found matching '{state.get('query')}'"
        else:
            message = f"Failed to search events: {result.get('error', 'Unknown error')}"

        return _with_summary(state, message)
    except Exception as e:
        return _with_summary(state, f"Error searching events: {str(e)}")


# Build the graph
graph_builder = StateGraph(State, output_schema=OutputState)
graph_builder.add_node("parse_intent", parse_intent)
graph_builder.add_node("create", create_event)
graph_builder.add_node("read", read_event)
graph_builder.add_node("search", search_event)
graph_builder.add_node("update", update_event)
graph_builder.add_node("delete", delete_event)
graph_builder.add_node("summarize_result", summarize_result)

graph_builder.add_edge(START, "parse_intent")
graph_builder.add_conditional_edges(
    "parse_intent",
    route_action,
    {
        "create": "create",
        "read": "read",
        "search": "search",
        "update": "update",
        "delete": "delete",
    },
)

for action in ("create", "read", "search", "update", "delete"):
    graph_builder.add_edge(action, END)

graph_builder.add_edge("summarize_result", END)

graph = graph_builder.compile(name="noon-agent")


def build_agent_graph() -> StateGraph:
    """Return the compiled graph for compatibility with earlier imports."""

    return graph


def invoke_agent(state: State) -> OutputState:
    """Convenience helper that runs the compiled graph."""

    result = graph.invoke(state)
    return {"summary": result.get("summary", "")}


# other ideas
# • - search_free_time – scan attendee calendars for the
#     earliest mutually available windows.
#   - propose_slots – generate a ranked shortlist
#     of candidate start/end times (with time‑zone
#     normalization).
#   - adjust_event – move an existing event by
#     ±N minutes/hours while keeping participant
#     constraints intact.
#   - sync_external – pull in events from external
#     sources (invites, shared calendars) and reconcile
#     duplicates.
#   - notify_attendees – draft/send updates or reminders
#     when an event is created, moved, or canceled.
#   - summarize_day – return a natural-language rundown
#     of the user’s schedule, conflicts, and gaps.
#   - set_preferences – store user defaults (meeting
#     lengths, working hours, buffer rules) for
#     downstream actions.
#   - resolve_conflict – pick which overlapping event
#     to keep, reschedule, or decline based on priority
#     rules.
#   - collect_requirements – gather missing metadata
#     (agenda, location, video link) before finalizing
#     an event.
