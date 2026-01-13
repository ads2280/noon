import logging
from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict
from typing import Literal, Any

logger = logging.getLogger(__name__)


class State(TypedDict):
    query: str
    auth: dict
    success: bool
    request: Literal[
        "show-event",
        "show-schedule",
        "create-event",
        "update-event",
        "delete-event",
        "no-action",
    ]
    metadata: dict[str, Any]


class OutputState(TypedDict):
    success: bool
    request: Literal[
        "show-event",
        "show-schedule",
        "create-event",
        "update-event",
        "delete-event",
        "no-action",
    ]
    metadata: dict[str, Any]


def hello_world(state: State) -> dict:
    """Simple hello world node that returns a greeting response."""
    query = state.get("query", "")
    logger.info(f"Hello World node executed with query: {query[:50]}...")
    
    # Return a simple hello world response in the format expected by the backend
    return {
        "success": True,
        "request": "no-action",
        "metadata": {
            "reason": f"Hello, World! You said: {query[:100] if query else 'nothing'}"
        }
    }


# Build the LangGraph
logger.info("Building LangGraph for hello world agent")

graph_builder = StateGraph(State, output_schema=OutputState)

# Add the hello world node
graph_builder.add_node("hello_world", hello_world)

# Start -> hello_world -> END
graph_builder.add_edge(START, "hello_world")
graph_builder.add_edge("hello_world", END)

# Compile the graph
graph = graph_builder.compile()

# Export as noon_graph (required by langgraph.json)
noon_graph = graph

logger.info("LangGraph compilation complete")
