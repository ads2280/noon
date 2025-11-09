"""LLM-based routing and intent classification for calendar operations."""

import json
from typing import Any, Dict, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .calendar_state import CalendarAgentState
from .config import get_settings
from .tools.context_tools import parse_relative_time

ROUTER_SYSTEM_PROMPT = """You are a calendar intent classifier for the Noon calendar agent.

Your job is to analyze user input and extract:
1. The intent (what action the user wants)
2. Parameters for that action

Available intents:
- create_event: Create a new calendar event
- update_event: Modify an existing event
- delete_event: Remove an event
- search_events: Search for events by text
- get_schedule: View schedule for a time period
- check_availability: Find free time slots
- find_overlap: Find mutual availability with others
- acknowledge: Simple greeting or non-action message

Respond with JSON in this exact format:
{
  "intent": "intent_name",
  "parameters": {
    // Parameters specific to the intent
  },
  "confidence": 0.95
}

For create_event, extract:
- summary (string): Event title
- start_datetime (ISO 8601 string or relative like "tomorrow 2pm")
- end_datetime (ISO 8601 string or relative like "tomorrow 3pm")
- description (string, optional)
- attendees (list of names/emails, optional)

For update_event, extract:
- event_id (string): Event identifier (may need to search first)
- Any fields to update (summary, start_datetime, end_datetime, etc.)

For delete_event, extract:
- event_id (string): Event to delete

For search_events, extract:
- query (string): Search query
- time_min (ISO 8601 or relative, optional)
- time_max (ISO 8601 or relative, optional)

For get_schedule, extract:
- time_min (ISO 8601 or relative)
- time_max (ISO 8601 or relative)

For check_availability, extract:
- time_min (ISO 8601 or relative)
- time_max (ISO 8601 or relative)
- duration_minutes (int, default 60)

For find_overlap, extract:
- friends (list of names)
- time_min (ISO 8601 or relative)
- time_max (ISO 8601 or relative)
- duration_minutes (int, default 60)

Context available:
- Current time: {current_time}
- User timezone: {timezone}
- Upcoming events: {upcoming_events}

Examples:

User: "Schedule a meeting with Alice tomorrow at 2pm"
Response: {
  "intent": "create_event",
  "parameters": {
    "summary": "Meeting with Alice",
    "start_datetime": "tomorrow 2pm",
    "end_datetime": "tomorrow 3pm",
    "attendees": ["Alice"]
  },
  "confidence": 0.9
}

User: "When am I free next week?"
Response: {
  "intent": "check_availability",
  "parameters": {
    "time_min": "next week",
    "time_max": "end of next week",
    "duration_minutes": 60
  },
  "confidence": 0.95
}

User: "Find a time when Bob and I are both free on Friday"
Response: {
  "intent": "find_overlap",
  "parameters": {
    "friends": ["Bob"],
    "time_min": "friday",
    "time_max": "end of friday",
    "duration_minutes": 60
  },
  "confidence": 0.9
}

Now analyze this user input and respond with JSON only:
"""


def route_intent_node(state: CalendarAgentState) -> Dict[str, Any]:
    """
    LLM-based routing node that classifies intent and extracts parameters.

    This node uses an LLM to:
    1. Determine the user's intent
    2. Extract relevant parameters
    3. Handle relative time expressions

    Updates state with:
    - intent: The classified intent
    - parameters: Extracted parameters for the intent
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.model,
        temperature=0.1,  # Low temperature for more deterministic routing
        api_key=settings.openai_api_key,
    )

    # Build context for the LLM
    upcoming_summary = (
        "\n".join(
            [
                f"- {e['summary']} at {e['start']}"
                for e in state["user_context"]["upcoming_events"][:5]
            ]
        )
        if state["user_context"]["upcoming_events"]
        else "None"
    )

    system_prompt = ROUTER_SYSTEM_PROMPT.format(
        current_time=state["current_time"].isoformat(),
        timezone=state["user_context"]["timezone"],
        upcoming_events=upcoming_summary,
    )

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state["input"])]

    # Call LLM to classify intent
    response = llm.invoke(messages)
    content = response.content

    # Parse JSON response
    try:
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed = json.loads(content)
        intent = parsed.get("intent")
        parameters = parsed.get("parameters", {})

        # Process relative time expressions
        parameters = _process_time_parameters(
            parameters, state["current_time"], state["user_context"]["timezone"]
        )

        return {
            **state,
            "intent": intent,
            "parameters": parameters,
        }

    except json.JSONDecodeError as e:
        return {
            **state,
            "error": f"Failed to parse LLM response: {str(e)}. Response was: {content}",
        }


def _process_time_parameters(
    parameters: Dict[str, Any], current_time, timezone: str
) -> Dict[str, Any]:
    """
    Process relative time expressions in parameters.

    Converts expressions like "tomorrow", "next week" to ISO 8601 timestamps.
    """
    processed = parameters.copy()

    # Handle start_datetime
    if "start_datetime" in processed:
        if not processed["start_datetime"].endswith("Z") and "T" not in processed["start_datetime"]:
            # Relative expression
            parsed = parse_relative_time(processed["start_datetime"], current_time, timezone)
            processed["start_datetime"] = parsed["start"]

    # Handle end_datetime
    if "end_datetime" in processed:
        if not processed["end_datetime"].endswith("Z") and "T" not in processed["end_datetime"]:
            parsed = parse_relative_time(processed["end_datetime"], current_time, timezone)
            processed["end_datetime"] = parsed["start"]

    # Handle time_min
    if "time_min" in processed:
        if not processed["time_min"].endswith("Z") and "T" not in processed["time_min"]:
            parsed = parse_relative_time(processed["time_min"], current_time, timezone)
            processed["time_min"] = parsed["start"]

    # Handle time_max
    if "time_max" in processed:
        if not processed["time_max"].endswith("Z") and "T" not in processed["time_max"]:
            parsed = parse_relative_time(processed["time_max"], current_time, timezone)
            processed["time_max"] = parsed["end"]

    return processed


def route_to_action(
    state: CalendarAgentState,
) -> Literal[
    "create_event",
    "update_event",
    "delete_event",
    "search_events",
    "get_schedule",
    "check_availability",
    "find_overlap",
    "acknowledge",
    "error",
]:
    """
    Conditional routing function that directs to the appropriate action node.

    This is called by LangGraph's conditional_edges to determine which node to execute next.
    """
    if state.get("error"):
        return "error"

    intent = state.get("intent")

    if intent == "create_event":
        return "create_event"
    elif intent == "update_event":
        return "update_event"
    elif intent == "delete_event":
        return "delete_event"
    elif intent == "search_events":
        return "search_events"
    elif intent == "get_schedule":
        return "get_schedule"
    elif intent == "check_availability":
        return "check_availability"
    elif intent == "find_overlap":
        return "find_overlap"
    elif intent == "acknowledge":
        return "acknowledge"
    else:
        return "error"


def acknowledge_node(state: CalendarAgentState) -> Dict[str, Any]:
    """Simple acknowledgment node for greetings."""
    return {
        **state,
        "response": "Hello! I can help you with your calendar. What would you like to do?",
    }
