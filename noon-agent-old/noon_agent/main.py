"""Noon agent - Simple Google Calendar operations with LangGraph."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, TypedDict, Union

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, TypeAdapter

from .calendar_service import CalendarServiceError
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

    if parsed.auth_token is None and state.get("auth_token"):
        next_state["auth_token"] = state.get("auth_token")

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


def create_event(state: State) -> State:
    """Return instructions for creating a calendar event."""

    logger.info("%s", "=" * 80)
    logger.info("CREATE_EVENT: Building instruction payload")

    event_title = state.get("name") or state.get("summary") or "New Event"
    description = state.get("description") or (state.get("summary") if state.get("name") else None)
    start_time = state.get("start_time")
    end_time = state.get("end_time")

    if not start_time or not end_time:
        raise CalendarServiceError("start_time and end_time are required to create an event")

    payload = CreateEventPayload(
        tool="create",
        id=state.get("event_id"),
        calendar=state.get("calendar_id") or (state.get("context") or {}).get("primary_calendar_id"),
        summary=event_title,
        description=description,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        attendees=state.get("people"),
        location=state.get("location"),
        metadata={
            "intent": "create",
            "source": "agent",
            "query": state.get("query"),
        },
    )

    logger.info("CREATE_EVENT: Instruction payload ready for summary=%s", event_title)
    logger.info("%s", "=" * 80)
    return _with_agent_result(state, payload)


def read_event(state: State) -> State:
    """Return instructions for showing one or more events."""

    logger.info("%s", "=" * 80)
    logger.info("READ_EVENT: Building instruction payload")

    payload = ShowEventPayload(
        tool="show",
        id=state.get("event_id") or "",
        calendar=state.get("calendar_id") or (state.get("context") or {}).get("primary_calendar_id"),
        event={
            "query": state.get("summary") or state.get("name") or state.get("query"),
            "time_min": state.get("start_time").isoformat() if state.get("start_time") else None,
            "time_max": state.get("end_time").isoformat() if state.get("end_time") else None,
        },
    )

    logger.info("READ_EVENT: Instruction payload ready (id=%s)", payload.id)
    logger.info("%s", "=" * 80)
    return _with_agent_result(state, payload)


def get_schedule(state: State) -> State:
    """Return instructions for showing a schedule over a range."""

    logger.info("%s", "=" * 80)
    logger.info("GET_SCHEDULE: Building instruction payload")

    start_time = state.get("start_time")
    end_time = state.get("end_time")
    if not start_time or not end_time:
        raise CalendarServiceError("start_time and end_time are required for schedule views")

    payload = ShowSchedulePayload(
        tool="show-schedule",
        start_day=start_time.date().isoformat(),
        end_day=end_time.date().isoformat(),
        events=None,
    )

    logger.info(
        "GET_SCHEDULE: Instruction payload ready start=%s end=%s",
        payload.start_day,
        payload.end_day,
    )
    logger.info("%s", "=" * 80)
    return _with_agent_result(state, payload)


def update_event(state: State) -> State:
    """Return instructions describing the requested event update."""

    logger.info("UPDATE_EVENT: Building instruction payload for event_id=%s", state.get("event_id"))

    event_id = state.get("event_id")
    if not event_id:
        raise CalendarServiceError("event_id is required to update an event")

    changes: Dict[str, Any] = {}
    if state.get("summary") or state.get("name"):
        changes["summary"] = state.get("summary") or state.get("name")
    if state.get("start_time"):
        changes["start_time"] = state["start_time"].isoformat()
    if state.get("end_time"):
        changes["end_time"] = state["end_time"].isoformat()
    if state.get("description"):
        changes["description"] = state["description"]
    if state.get("people"):
        changes["attendees"] = state["people"]
    if state.get("location"):
        changes["location"] = state["location"]

    if not changes:
        changes["status"] = "No fields updated"

    payload = UpdateEventPayload(
        tool="update",
        id=event_id,
        calendar=state.get("calendar_id"),
        changes=changes,
    )

    logger.info("UPDATE_EVENT: Instruction payload ready for id=%s", payload.id)
    return _with_agent_result(state, payload)


def delete_event(state: State) -> State:
    """Return instructions describing the requested event deletion."""

    logger.info("DELETE_EVENT: Building instruction payload for event_id=%s", state.get("event_id"))

    event_id = state.get("event_id")
    if not event_id:
        raise CalendarServiceError("event_id is required to delete an event")

    payload = DeleteEventPayload(
        tool="delete",
        id=event_id,
        calendar=state.get("calendar_id"),
    )

    logger.info("DELETE_EVENT: Instruction payload ready for id=%s", payload.id)
    return _with_agent_result(state, payload)


def search_event(state: State) -> State:
    """Return instructions for searching events."""

    logger.info("SEARCH_EVENT: Building instruction payload")

    search_term = state.get("summary") or state.get("name") or state.get("query")

    payload = ShowEventPayload(
        tool="show",
        id=state.get("event_id") or "",
        calendar=state.get("calendar_id"),
        event={
            "query": search_term,
            "time_min": state.get("start_time").isoformat() if state.get("start_time") else None,
            "time_max": state.get("end_time").isoformat() if state.get("end_time") else None,
        },
    )

    logger.info("SEARCH_EVENT: Instruction payload ready for query=%s", search_term)
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
