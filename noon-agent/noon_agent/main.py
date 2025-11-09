"""Noon agent - Simple Google Calendar operations with LangGraph."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, TypedDict, Union

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, TypeAdapter

from .calendar_service import CalendarService, CalendarServiceError
from .constants import self
from .helpers import build_intent_parser
from .schemas import (
    AgentQuery,
    AgentResponse,
    CreateEventPayload,
    DeleteEventPayload,
    ShowEventPayload,
    ShowSchedulePayload,
    UpdateEventPayload,
)

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


AgentPayload = Union[
    ShowEventPayload,
    ShowSchedulePayload,
    CreateEventPayload,
    UpdateEventPayload,
    DeleteEventPayload,
]


class State(TypedDict, total=False):
    """Internal state propagated between graph nodes."""

    query: str
    context: Dict[str, Any]
    action: Literal["create", "delete", "update", "read", "search", "schedule"]
    start_time: datetime | None
    end_time: datetime | None
    location: str | None
    people: List[str] | None
    name: str | None
    auth_provider: str | None
    auth_token: str | None
    summary: str | None
    calendar_id: str | None
    event_id: str | None
    description: str | None
    agent_result: AgentPayload | None


calendar_service = CalendarService()
agent_response_adapter = TypeAdapter(AgentResponse)


def route_action(state: State) -> str:
    """Select the next node based on requested action; default to read."""

    action = state.get("action", "read")
    logger.info("ROUTE_ACTION: Routing to action: %s", action)
    return action


def get_intent_chain() -> Runnable:
    return build_intent_parser()


def parse_intent(state: State) -> State:
    """Call the LLM to normalize the user's scheduling intent."""

    logger.info("%s", "=" * 80)
    logger.info("PARSE_INTENT: Starting intent parsing")

    query_text = state.get("query", "")
    if not query_text:
        raise ValueError("Missing query text for intent parsing")

    logger.info("PARSE_INTENT: User query: %s", query_text)

    normalized_messages: List[Dict[str, Any]] = [{"role": "human", "content": query_text}]

    logger.info("PARSE_INTENT: Calling LLM to extract structured intent...")
    parsed = get_intent_chain().invoke({"messages": normalized_messages})
    next_state = dict(state)
    next_state.update(parsed.model_dump())

    logger.info("PARSE_INTENT: Parsed intent - action=%s", next_state.get("action"))
    logger.info("PARSE_INTENT: Parsed intent - name=%s", next_state.get("name"))
    logger.info("PARSE_INTENT: Parsed intent - summary=%s", next_state.get("summary"))
    logger.info("PARSE_INTENT: Parsed intent - start_time=%s", next_state.get("start_time"))
    logger.info("PARSE_INTENT: Parsed intent - end_time=%s", next_state.get("end_time"))
    logger.info("PARSE_INTENT: Parsed intent - people=%s", next_state.get("people"))
    logger.info("PARSE_INTENT: Parsed intent - location=%s", next_state.get("location"))

    # Ensure self user is always included in people list for create/update actions
    if next_state.get("action") in ["create", "update"]:
        self_email = list(self.values())[0] if self else None
        if self_email:
            people = next_state.get("people") or []
            if self_email not in people:
                logger.info("PARSE_INTENT: Adding self user %s to people list", self_email)
                people.append(self_email)
            next_state["people"] = people
            logger.info("PARSE_INTENT: Final people list: %s", next_state["people"])

    logger.info("PARSE_INTENT: Intent parsing complete")
    logger.info("%s", "=" * 80)
    return next_state


def _with_agent_result(state: State, payload: AgentPayload) -> State:
    next_state = dict(state)
    next_state["agent_result"] = payload
    return next_state


def _ensure_success(result: Dict[str, Any], error_prefix: str) -> None:
    if result.get("status") != "success":
        raise CalendarServiceError(f"{error_prefix}: {result.get('error', 'Unknown error')}")


def create_event(state: State) -> State:
    """Create a calendar event using Google Calendar API."""

    logger.info("%s", "=" * 80)
    logger.info("CREATE_EVENT: Starting event creation")

    event_title = state.get("name") or state.get("summary") or "New Event"
    description = state.get("description") or (state.get("summary") if state.get("name") else None)
    start_time = state.get("start_time")
    end_time = state.get("end_time")

    logger.info("CREATE_EVENT: Event title=%s", event_title)
    logger.info("CREATE_EVENT: Start=%s End=%s", start_time, end_time)

    result = calendar_service.create_event(
        auth_token=state.get("auth_token"),
        summary=event_title,
        start_time=start_time,
        end_time=end_time,
        description=description,
        attendees=state.get("people"),
        calendar_id=state.get("calendar_id"),
        context=state.get("context"),
    )

    _ensure_success(result, "CREATE_EVENT")

    payload = CreateEventPayload(
        tool="create",
        id=result.get("event_id"),
        calendar=result.get("calendar_id"),
        summary=event_title,
        description=description,
        start_time=result.get("start"),
        end_time=result.get("end"),
        attendees=state.get("people"),
        location=state.get("location"),
        conference_link=result.get("link"),
        metadata={"service_result": result},
    )

    logger.info("CREATE_EVENT: Created event id=%s", payload.id)
    logger.info("%s", "=" * 80)
    return _with_agent_result(state, payload)


def _select_primary_event(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not events:
        raise CalendarServiceError("No events available for display")
    return events[0]


def read_event(state: State) -> State:
    """Read/list calendar events using Google Calendar API and surface one to display."""

    logger.info("%s", "=" * 80)
    logger.info("READ_EVENT: Starting event read")

    result = calendar_service.read_events(
        auth_token=state.get("auth_token"),
        calendar_id=state.get("calendar_id"),
        context=state.get("context"),
        time_min=state.get("start_time"),
        time_max=state.get("end_time"),
        query=state.get("summary") or state.get("name") or state.get("query"),
    )

    _ensure_success(result, "READ_EVENT")
    events = result.get("events", [])
    primary = _select_primary_event(events)

    payload = ShowEventPayload(
        tool="show",
        id=primary["event_id"],
        calendar=primary.get("calendar_id"),
        event={
            "selected": primary,
            "matches": events,
        },
    )

    logger.info("READ_EVENT: Returning event id=%s", payload.id)
    logger.info("%s", "=" * 80)
    return _with_agent_result(state, payload)


def get_schedule(state: State) -> State:
    """Retrieve a schedule view across a date range."""

    logger.info("%s", "=" * 80)
    logger.info("GET_SCHEDULE: Starting schedule retrieval")

    start_time = state.get("start_time")
    end_time = state.get("end_time")
    if not start_time or not end_time:
        raise CalendarServiceError("start_time and end_time are required for schedule views")

    result = calendar_service.get_schedule(
        auth_token=state.get("auth_token"),
        calendar_id=state.get("calendar_id"),
        context=state.get("context"),
        start_time=start_time,
        end_time=end_time,
    )

    _ensure_success(result, "GET_SCHEDULE")

    payload = ShowSchedulePayload(
        tool="show-schedule",
        start_day=start_time.date().isoformat(),
        end_day=end_time.date().isoformat(),
        events=result.get("events", []),
    )

    logger.info(
        "GET_SCHEDULE: Returning schedule start=%s end=%s", payload.start_day, payload.end_day
    )
    logger.info("%s", "=" * 80)
    return _with_agent_result(state, payload)


def update_event(state: State) -> State:
    """Update a calendar event using Google Calendar API."""

    logger.info("UPDATE_EVENT: Updating event_id=%s", state.get("event_id"))

    result = calendar_service.update_event(
        auth_token=state.get("auth_token"),
        event_id=state.get("event_id"),
        summary=state.get("summary") or state.get("name"),
        start_time=state.get("start_time"),
        end_time=state.get("end_time"),
        description=state.get("description"),
        calendar_id=state.get("calendar_id"),
        context=state.get("context"),
    )

    _ensure_success(result, "UPDATE_EVENT")

    changes: Dict[str, Any] = {}
    if result.get("summary"):
        changes["summary"] = result["summary"]
    if result.get("start"):
        changes["start_time"] = result["start"]
    if result.get("end"):
        changes["end_time"] = result["end"]
    if state.get("description"):
        changes["description"] = state["description"]

    if not changes:
        changes["status"] = "No fields updated"

    payload = UpdateEventPayload(
        tool="update",
        id=result.get("event_id") or state.get("event_id") or "",
        calendar=result.get("calendar_id") or state.get("calendar_id"),
        changes=changes,
    )

    logger.info("UPDATE_EVENT: Returning payload for id=%s", payload.id)
    return _with_agent_result(state, payload)


def delete_event(state: State) -> State:
    """Delete a calendar event using Google Calendar API."""

    logger.info("DELETE_EVENT: Deleting event_id=%s", state.get("event_id"))

    result = calendar_service.delete_event(
        auth_token=state.get("auth_token"),
        event_id=state.get("event_id"),
        calendar_id=state.get("calendar_id"),
        context=state.get("context"),
    )

    _ensure_success(result, "DELETE_EVENT")

    payload = DeleteEventPayload(
        tool="delete",
        id=result.get("event_id") or state.get("event_id") or "",
        calendar=result.get("calendar_id") or state.get("calendar_id"),
    )

    logger.info("DELETE_EVENT: Returning payload for id=%s", payload.id)
    return _with_agent_result(state, payload)


def search_event(state: State) -> State:
    """Search calendar events using free text query."""

    logger.info("SEARCH_EVENT: Searching events")

    search_term = state.get("summary") or state.get("name") or state.get("query")
    result = calendar_service.search_events(
        auth_token=state.get("auth_token"),
        query=search_term,
        calendar_id=state.get("calendar_id"),
        context=state.get("context"),
        time_min=state.get("start_time"),
        time_max=state.get("end_time"),
    )

    _ensure_success(result, "SEARCH_EVENT")

    events = result.get("events", [])
    primary = _select_primary_event(events)

    payload = ShowEventPayload(
        tool="show",
        id=primary["event_id"],
        calendar=primary.get("calendar_id"),
        event={
            "query": search_term,
            "selected": primary,
            "matches": events,
        },
    )

    logger.info("SEARCH_EVENT: Returning event id=%s", payload.id)
    return _with_agent_result(state, payload)


# Build the graph
graph_builder = StateGraph(State)
graph_builder.add_node("parse_intent", parse_intent)
graph_builder.add_node("create", create_event)
graph_builder.add_node("read", read_event)
graph_builder.add_node("search", search_event)
graph_builder.add_node("update", update_event)
graph_builder.add_node("delete", delete_event)
graph_builder.add_node("schedule", get_schedule)

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
        "schedule": "schedule",
    },
)

for action in ("create", "read", "search", "update", "delete", "schedule"):
    graph_builder.add_edge(action, END)


graph = graph_builder.compile(name="noon-agent")


def build_agent_graph() -> StateGraph:
    """Return the compiled graph for compatibility with earlier imports."""

    return graph


def _coerce_agent_query(payload: AgentQuery | Dict[str, Any]) -> AgentQuery:
    if isinstance(payload, AgentQuery):
        return payload
    if isinstance(payload, dict):
        return AgentQuery(**payload)
    raise TypeError("Payload must be an AgentQuery or dict")


def invoke_agent(payload: AgentQuery | Dict[str, Any]) -> Dict[str, Any]:
    """Run the compiled graph and return a structured AgentResponse payload."""

    request = _coerce_agent_query(payload)
    initial_state: State = {
        "query": request.query,
        "context": request.context or {},
    }

    if request.auth_token:
        initial_state["auth_token"] = request.auth_token
    if request.calendar_id:
        initial_state["calendar_id"] = request.calendar_id

    result_state = graph.invoke(initial_state)
    agent_result = result_state.get("agent_result")
    if agent_result is None:
        raise RuntimeError("Agent graph completed without producing a result payload")

    if isinstance(agent_result, BaseModel):
        data = agent_result.model_dump(exclude_none=True)
    elif isinstance(agent_result, dict):
        data = agent_result
    else:
        raise RuntimeError("Agent result is of unexpected type")

    validated = agent_response_adapter.validate_python(data)
    if isinstance(validated, BaseModel):
        return validated.model_dump(exclude_none=True)
    return validated  # pragma: no cover
