import logging
from langgraph.graph import StateGraph, END, START
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from typing import Literal, Any, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from . import prompts

logger = logging.getLogger(__name__)
llm = init_chat_model(
    "openai:gpt-5-nano",
    temperature=0.7,
    configurable_fields=("temperature", "max_tokens", "model"),
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


# Pydantic schemas for structured LLM outputs
class IntentClassification(BaseModel):
    """Classification of user intent into one of six request types."""

    request: Literal[
        "show-event",
        "show-schedule",
        "create-event",
        "update-event",
        "delete-event",
        "no-action",
    ]
    reasoning: str = Field(
        description="Brief explanation of why this intent was chosen"
    )


class ShowEventExtraction(BaseModel):
    """Extract event identifier information for searching."""

    event_title: str = Field(description="The title or name of the event to find")
    event_description: Optional[str] = Field(
        default=None, description="Additional description or details about the event"
    )


class ShowScheduleExtraction(BaseModel):
    """Extract date range for schedule viewing."""

    start_time: str = Field(
        description="Start datetime in ISO 8601 format with timezone (YYYY-MM-DDTHH:MM:SS±HH:MM or YYYY-MM-DDTHH:MM:SSZ)",
        alias="start-time",
    )
    end_time: str = Field(
        description="End datetime in ISO 8601 format with timezone (YYYY-MM-DDTHH:MM:SS±HH:MM or YYYY-MM-DDTHH:MM:SSZ)",
        alias="end-time",
    )

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_iso_datetime_with_timezone(cls, v: str) -> str:
        """Validate that the string is in ISO 8601 format with timezone and includes time component."""
        if not v:
            raise ValueError("Datetime string cannot be empty")

        # Check for time component (must have 'T' separator)
        if "T" not in v:
            raise ValueError("Must include time component (YYYY-MM-DDTHH:MM:SS format)")

        # Check for timezone (must have 'Z' or '+'/'-' timezone offset)
        if not (v.endswith("Z") or "+" in v.split("T")[1] or "-" in v.split("T")[1]):
            raise ValueError("Must include timezone (Z or ±HH:MM offset)")

        try:
            # Parse to validate format
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError as e:
            raise ValueError(
                f"Must be valid ISO 8601 datetime format with timezone: {e}"
            )

    class Config:
        populate_by_name = True


class CreateEventExtraction(BaseModel):
    """Extract all information needed to create a calendar event."""

    title: str = Field(description="Event title")
    start_time: str = Field(
        description="Start datetime in ISO 8601 format with timezone (YYYY-MM-DDTHH:MM:SS±HH:MM or YYYY-MM-DDTHH:MM:SSZ)",
        alias="start-time",
    )
    end_time: str = Field(
        description="End datetime in ISO 8601 format with timezone (YYYY-MM-DDTHH:MM:SS±HH:MM or YYYY-MM-DDTHH:MM:SSZ)",
        alias="end-time",
    )
    location: Optional[str] = Field(default=None, description="Event location")
    attendees: Optional[list[str]] = Field(
        default=None, description="List of attendee email addresses"
    )
    description: Optional[str] = Field(default=None, description="Event description")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_iso_datetime_with_timezone(cls, v: str) -> str:
        """Validate that the string is in ISO 8601 format with timezone and includes time component."""
        if not v:
            raise ValueError("Datetime string cannot be empty")

        # Check for time component (must have 'T' separator)
        if "T" not in v:
            raise ValueError("Must include time component (YYYY-MM-DDTHH:MM:SS format)")

        # Check for timezone (must have 'Z' or '+'/'-' timezone offset)
        if not (v.endswith("Z") or "+" in v.split("T")[1] or "-" in v.split("T")[1]):
            raise ValueError("Must include timezone (Z or ±HH:MM offset)")

        try:
            # Parse to validate format
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError as e:
            raise ValueError(
                f"Must be valid ISO 8601 datetime format with timezone: {e}"
            )

    class Config:
        populate_by_name = True


class UpdateEventExtraction(BaseModel):
    """Extract event identifier and new information for updating."""

    event_title: str = Field(description="Current title of the event to update")
    new_title: Optional[str] = Field(
        default=None, description="New event title if changing"
    )
    new_start_time: Optional[str] = Field(
        default=None,
        description="New start datetime in ISO 8601 format with timezone (YYYY-MM-DDTHH:MM:SS±HH:MM or YYYY-MM-DDTHH:MM:SSZ)",
        alias="new-start-time",
    )
    new_end_time: Optional[str] = Field(
        default=None,
        description="New end datetime in ISO 8601 format with timezone (YYYY-MM-DDTHH:MM:SS±HH:MM or YYYY-MM-DDTHH:MM:SSZ)",
        alias="new-end-time",
    )
    new_location: Optional[str] = Field(
        default=None, description="New location if changing"
    )
    new_attendees: Optional[list[str]] = Field(
        default=None, description="New attendee list if changing"
    )
    new_description: Optional[str] = Field(
        default=None, description="New description if changing"
    )

    @field_validator("new_start_time", "new_end_time")
    @classmethod
    def validate_iso_datetime_with_timezone(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the string is in ISO 8601 format with timezone and includes time component."""
        # Allow None for optional fields
        if v is None:
            return v

        if not v:
            raise ValueError("Datetime string cannot be empty")

        # Check for time component (must have 'T' separator)
        if "T" not in v:
            raise ValueError("Must include time component (YYYY-MM-DDTHH:MM:SS format)")

        # Check for timezone (must have 'Z' or '+'/'-' timezone offset)
        if not (v.endswith("Z") or "+" in v.split("T")[1] or "-" in v.split("T")[1]):
            raise ValueError("Must include timezone (Z or ±HH:MM offset)")

        try:
            # Parse to validate format
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except ValueError as e:
            raise ValueError(
                f"Must be valid ISO 8601 datetime format with timezone: {e}"
            )

    class Config:
        populate_by_name = True


class DeleteEventExtraction(BaseModel):
    """Extract event identifier for deletion."""

    event_title: str = Field(description="The title or name of the event to delete")
    event_description: Optional[str] = Field(
        default=None, description="Additional description to help identify the event"
    )


def llm_step(state: State) -> dict:
    """Classify user intent from query string into one of six request types."""
    logger.info(f"Classifying intent for query: {state['query']}")

    structured_llm = llm.with_structured_output(IntentClassification)
    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompts.INTENT_CLASSIFICATION_PROMPT},
            {"role": "user", "content": state["query"]},
        ]
    )

    logger.info(
        f"Classified intent as: {result.request} (reasoning: {result.reasoning})"
    )
    return {"request": result.request}


def show_event(state: State) -> dict:
    """Extract event identifier and search for it in calendar.

    TODO: When backend calendar utils are ready, add API call to search by title
    and retrieve actual event-id and calendar-id.
    """
    logger.info(f"Extracting event identifier from query: {state['query']}")

    structured_llm = llm.with_structured_output(ShowEventExtraction)
    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompts.SHOW_EVENT_PROMPT},
            {"role": "user", "content": state["query"]},
        ]
    )

    logger.info(f"Extracted event info - Title: {result.event_title}")

    # TODO: Replace with actual API call to search calendar by title
    # Example: event = calendar_api.search_event(result.event_title, state['auth'])
    # For now, return placeholder IDs
    return {
        "success": True,
        "metadata": {
            "event-id": "placeholder-event-id",
            "calendar-id": "placeholder-calendar-id",
            # Store search criteria for backend to use
            "search-title": result.event_title,
            "search-description": result.event_description,
        },
    }


def show_schedule(state: State) -> dict:
    """Parse natural language date queries and extract date range.

    Examples: "what am I doing next weekend", "tomorrow", "next Monday"
    """
    logger.info(f"Extracting date range from query: {state['query']}")

    structured_llm = llm.with_structured_output(ShowScheduleExtraction)
    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompts.SHOW_SCHEDULE_PROMPT},
            {"role": "user", "content": state["query"]},
        ]
    )

    logger.info(
        f"Extracted date range - Start: {result.start_time}, End: {result.end_time}"
    )

    return {
        "success": True,
        "metadata": {"start-time": result.start_time, "end-time": result.end_time},
    }


def create_event(state: State) -> dict:
    """Extract all event details needed to create a new calendar event.

    Extracts: title, start-time, end-time, location, attendees, description
    """
    logger.info(f"Extracting event creation details from query: {state['query']}")

    structured_llm = llm.with_structured_output(CreateEventExtraction)
    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompts.CREATE_EVENT_PROMPT},
            {"role": "user", "content": state["query"]},
        ]
    )

    logger.info(
        f"Extracted event details - Title: {result.title}, Start: {result.start_time}, End: {result.end_time}"
    )

    # Build metadata dict with all event fields
    metadata = {
        "title": result.title,
        "start-time": result.start_time,
        "end-time": result.end_time,
    }

    # Add optional fields if present
    if result.location:
        metadata["location"] = result.location
    if result.attendees:
        metadata["attendees"] = result.attendees
    if result.description:
        metadata["description"] = result.description

    return {"success": True, "metadata": metadata}


def update_event(state: State) -> dict:
    """Extract event identifier and new event details for updating.

    TODO: When backend calendar utils are ready, add API call to search by title
    and retrieve actual event-id and calendar-id.
    """
    logger.info(f"Extracting event update details from query: {state['query']}")

    structured_llm = llm.with_structured_output(UpdateEventExtraction)
    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompts.UPDATE_EVENT_PROMPT},
            {"role": "user", "content": state["query"]},
        ]
    )

    logger.info(f"Extracted update for event: {result.event_title}")

    # TODO: Replace with actual API call to search calendar by title
    # Example: event = calendar_api.search_event(result.event_title, state['auth'])
    # For now, use placeholder IDs
    metadata = {
        "event-id": "placeholder-event-id",
        "calendar-id": "placeholder-calendar-id",
        # Store search criteria for backend to use
        "search-title": result.event_title,
    }

    # Add all new event fields if they were specified
    if result.new_title:
        metadata["title"] = result.new_title
    if result.new_start_time:
        metadata["start-time"] = result.new_start_time
    if result.new_end_time:
        metadata["end-time"] = result.new_end_time
    if result.new_location:
        metadata["location"] = result.new_location
    if result.new_attendees:
        metadata["attendees"] = result.new_attendees
    if result.new_description:
        metadata["description"] = result.new_description

    return {"success": True, "metadata": metadata}


def delete_event(state: State) -> dict:
    """Extract event identifier for deletion.

    TODO: When backend calendar utils are ready, add API call to search by title
    and retrieve actual event-id and calendar-id.
    """
    logger.info(f"Extracting event deletion details from query: {state['query']}")

    structured_llm = llm.with_structured_output(DeleteEventExtraction)
    result = structured_llm.invoke(
        [
            {"role": "system", "content": prompts.DELETE_EVENT_PROMPT},
            {"role": "user", "content": state["query"]},
        ]
    )

    logger.info(f"Extracted event to delete: {result.event_title}")

    # TODO: Replace with actual API call to search calendar by title
    # Example: event = calendar_api.search_event(result.event_title, state['auth'])
    # For now, return placeholder IDs
    return {
        "success": True,
        "metadata": {
            "event-id": "placeholder-event-id",
            "calendar-id": "placeholder-calendar-id",
            # Store search criteria for backend to use
            "search-title": result.event_title,
            "search-description": result.event_description,
        },
    }


def do_nothing(state: State) -> dict:
    """Placeholder for no-action case."""
    logger.info(f"No action needed for query: {state['query']}")
    return {"success": True, "metadata": {"reason": "No calendar action needed"}}


# Router function to determine which handler to call based on classified intent
def route_request(state: State) -> str:
    """Route to appropriate handler based on classified request type."""
    request_type = state["request"]
    logger.info(f"Routing to handler: {request_type}")
    return request_type


# Build the LangGraph
logger.info("Building LangGraph for calendar agent")

graph_builder = StateGraph(State, output_schema=OutputState)

# Add all nodes
graph_builder.add_node("classify_intent", llm_step)
graph_builder.add_node("show-event", show_event)
graph_builder.add_node("show-schedule", show_schedule)
graph_builder.add_node("create-event", create_event)
graph_builder.add_node("update-event", update_event)
graph_builder.add_node("delete-event", delete_event)
graph_builder.add_node("no-action", do_nothing)

# Start -> classify intent
graph_builder.add_edge(START, "classify_intent")

# Conditional routing from classify_intent to appropriate handler
graph_builder.add_conditional_edges(
    "classify_intent",
    route_request,
    {
        "show-event": "show-event",
        "show-schedule": "show-schedule",
        "create-event": "create-event",
        "update-event": "update-event",
        "delete-event": "delete-event",
        "no-action": "no-action",
    },
)

# All handlers -> END
graph_builder.add_edge("show-event", END)
graph_builder.add_edge("show-schedule", END)
graph_builder.add_edge("create-event", END)
graph_builder.add_edge("update-event", END)
graph_builder.add_edge("delete-event", END)
graph_builder.add_edge("no-action", END)

# Compile the graph
graph = graph_builder.compile()

# Export as noon_graph (required by langgraph.json)
noon_graph = graph

logger.info("LangGraph compilation complete")
