"""Complete LangGraph implementation for the Noon calendar agent."""

from datetime import datetime
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from .calendar_nodes import (
    check_availability_node,
    clarification_node,
    create_event_node,
    delete_event_node,
    error_node,
    find_overlap_node,
    get_schedule_node,
    search_events_node,
    update_event_node,
)
from .calendar_router import acknowledge_node, route_intent_node, route_to_action
from .calendar_state import CalendarAgentState


def build_calendar_graph():
    """
    Build and compile the calendar agent LangGraph.

    Graph structure:
    START -> route_intent -> [conditional routing to action nodes] -> END

    The graph supports:
    - Intent classification via LLM
    - Multiple calendar overlay
    - Friend resolution
    - Error handling
    - Clarifications
    """
    # Create the graph
    graph = StateGraph(CalendarAgentState)

    # Add all nodes
    graph.add_node("route_intent", route_intent_node)
    graph.add_node("create_event", create_event_node)
    graph.add_node("update_event", update_event_node)
    graph.add_node("delete_event", delete_event_node)
    graph.add_node("search_events", search_events_node)
    graph.add_node("get_schedule", get_schedule_node)
    graph.add_node("check_availability", check_availability_node)
    graph.add_node("find_overlap", find_overlap_node)
    graph.add_node("acknowledge", acknowledge_node)
    graph.add_node("error", error_node)
    graph.add_node("clarification", clarification_node)

    # Add edges
    # Start -> route_intent
    graph.add_edge(START, "route_intent")

    # Conditional routing from route_intent to action nodes
    graph.add_conditional_edges(
        "route_intent",
        route_to_action,
        {
            "create_event": "create_event",
            "update_event": "update_event",
            "delete_event": "delete_event",
            "search_events": "search_events",
            "get_schedule": "get_schedule",
            "check_availability": "check_availability",
            "find_overlap": "find_overlap",
            "acknowledge": "acknowledge",
            "error": "error",
        },
    )

    # All action nodes go to END
    graph.add_edge("create_event", END)
    graph.add_edge("update_event", END)
    graph.add_edge("delete_event", END)
    graph.add_edge("search_events", END)
    graph.add_edge("get_schedule", END)
    graph.add_edge("check_availability", END)
    graph.add_edge("find_overlap", END)
    graph.add_edge("acknowledge", END)
    graph.add_edge("error", END)
    graph.add_edge("clarification", END)

    # Compile the graph
    compiled_graph = graph.compile()

    return compiled_graph


def invoke_calendar_agent(
    user_input: str,
    user_context: Dict[str, Any],
    current_time: datetime = None,
) -> Dict[str, Any]:
    """
    Convenience function to invoke the calendar agent.

    Args:
        user_input: User's natural language input
        user_context: User context dict (includes access_token, timezone, etc.)
        current_time: Current timestamp (defaults to now)

    Returns:
        Final state after graph execution
    """
    graph = build_calendar_graph()

    if current_time is None:
        current_time = datetime.now()

    initial_state: CalendarAgentState = {
        "input": user_input,
        "current_time": current_time,
        "user_context": user_context,
        "intent": None,
        "parameters": None,
        "result": None,
        "needs_clarification": False,
        "clarification_message": None,
        "clarification_options": None,
        "error": None,
        "response": None,
    }

    final_state = graph.invoke(initial_state)

    return final_state
