"""LangGraph entrypoints for the Noon agent (legacy - deprecated).

DEPRECATED: This is a placeholder implementation for backwards compatibility.
Use `calendar_graph.py` and `invoke_calendar_agent()` for the real calendar agent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict, total=False):
    """Internal state propagated between graph nodes."""

    action: Literal["create", "delete", "update", "read"]
    start_time: datetime | None
    end_time: datetime | None
    auth: Dict[str, Any]
    summary: str


class OutputState(TypedDict):
    """Output state returned by the graph."""

    summary: str


def route_action(state: State) -> str:
    """Select the next node based on requested action; default to read."""
    return state.get("action", "read")


def _with_summary(state: State, message: str) -> State:
    """Helper to add summary to state."""
    next_state = dict(state)
    next_state["summary"] = message
    return next_state


def create_event(state: State) -> State:
    """Placeholder for creating an event."""
    return _with_summary(state, "Created event (placeholder).")


def read_event(state: State) -> State:
    """Placeholder for reading an event."""
    return _with_summary(state, "Fetched event details (placeholder).")


def update_event(state: State) -> State:
    """Placeholder for updating an event."""
    return _with_summary(state, "Updated event (placeholder).")


def delete_event(state: State) -> State:
    """Placeholder for deleting an event."""
    return _with_summary(state, "Deleted event (placeholder).")


# Build the legacy graph
graph_builder = StateGraph(State, output_schema=OutputState)
graph_builder.add_node("create", create_event)
graph_builder.add_node("read", read_event)
graph_builder.add_node("update", update_event)
graph_builder.add_node("delete", delete_event)

graph_builder.add_conditional_edges(
    START,
    route_action,
    {
        "create": "create",
        "read": "read",
        "update": "update",
        "delete": "delete",
    },
)

for action in ("create", "read", "update", "delete"):
    graph_builder.add_edge(action, END)

graph = graph_builder.compile(name="noon-agent")


def build_agent_graph() -> StateGraph:
    """
    Return the compiled graph for compatibility with earlier imports.

    DEPRECATED: Use build_calendar_graph() instead.
    """
    return graph


def invoke_agent(state: State) -> OutputState:
    """
    Convenience helper that runs the compiled graph.

    DEPRECATED: Use invoke_calendar_agent() instead.
    """
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
