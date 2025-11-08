"""LangGraph entrypoints for the Noon agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.runnables import Runnable

from .helpers import build_intent_parser


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
    auth: Dict[str, Any]
    summary: str
    response: str
    success: bool


class OutputState(TypedDict):
    response: str
    success: bool


def route_action(state: State) -> str:
    """Select the next node based on requested action; default to read."""

    return state.get("action", "read")


intent_chain: Runnable = build_intent_parser()


def parse_intent(state: State) -> State:
    """Call the LLM to normalize the user's scheduling intent."""

    raw_messages = state.get("messages") or ""
    if isinstance(raw_messages, str):
        normalized_messages: List[Dict[str, Any]] = [{"role": "human", "content": raw_messages}]
    else:
        normalized_messages = raw_messages

    parsed = intent_chain.invoke({"messages": normalized_messages})
    next_state = dict(state)
    next_state.update(parsed.model_dump())
    return next_state


def _with_summary(state: State, message: str) -> State:
    next_state = dict(state)
    next_state["summary"] = message
    return next_state


def create_event(state: State) -> State:
    return _with_summary(state, "Created event (placeholder).")


def read_event(state: State) -> State:
    return _with_summary(state, "Fetched event details (placeholder).")


def update_event(state: State) -> State:
    return _with_summary(state, "Updated event (placeholder).")


def delete_event(state: State) -> State:
    return _with_summary(state, "Deleted event (placeholder).")


def summarize_result(state: State) -> OutputState:
    """Return a user-facing description of what the graph just did."""

    summary = state.get("summary") or "No additional details were provided."
    action = state.get("action", "read")
    result = f"{action.capitalize()} action completed: {summary}"
    return {"response": result, "success": True}


graph_builder = StateGraph(State, output_schema=OutputState)
graph_builder.add_node("parse_intent", parse_intent)
graph_builder.add_node("create", create_event)
graph_builder.add_node("read", read_event)
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
        "update": "update",
        "delete": "delete",
    },
)

for action in ("create", "read", "update", "delete"):
    graph_builder.add_edge(action, "summarize_result")

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
