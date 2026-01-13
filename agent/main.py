import logging
import os
from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict
from typing import Literal, Any
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI LLM
# ChatOpenAI will automatically read OPENAI_API_KEY from environment
# if not explicitly provided, so we don't need to pass it explicitly
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEY not found in environment variables - LLM calls may fail")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
)


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
    """Simple hello world node that uses OpenAI LLM to generate a greeting response."""
    query = state.get("query", "")
    logger.info(f"Hello World node executed with query: {query[:50]}...")
    
    # Use LLM to generate a response
    try:
        from langchain_core.messages import HumanMessage
        
        prompt_text = f"Say hello and respond to this query: {query[:500] if query else 'nothing'}"
        messages = [HumanMessage(content=prompt_text)]
        logger.info(f"Invoking LLM with prompt: {prompt_text[:100]}...")
        response = llm.invoke(messages)
        llm_response = response.content if hasattr(response, 'content') else str(response)
        logger.info(f"LLM generated response: {llm_response[:100]}...")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error invoking LLM: {error_msg}", exc_info=True)
        # Include the actual error in the response for debugging
        llm_response = f"Hello, World! I encountered an error: {error_msg[:200]}"
    
    # Return the LLM response in the format expected by the backend
    return {
        "success": True,
        "request": "no-action",
        "metadata": {
            "reason": llm_response
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
