"""Simple Google Calendar agent for the Noon project."""

from .calendar_service import CalendarService, CalendarServiceError
from .gcal_wrapper import (
    create_calendar_event,
    delete_calendar_event,
    get_calendar_service,
    read_calendar_events,
    search_calendar_events,
    update_calendar_event,
)
from .main import State, build_agent_graph, invoke_agent
from .schemas import AgentQuery, AgentResponse

__all__ = [
    # Calendar abstraction
    "CalendarService",
    "CalendarServiceError",
    # Calendar service
    "get_calendar_service",
    # Calendar operations
    "create_calendar_event",
    "read_calendar_events",
    "search_calendar_events",
    "update_calendar_event",
    "delete_calendar_event",
    # Agent graph
    "build_agent_graph",
    "invoke_agent",
    "State",
    "AgentQuery",
    "AgentResponse",
]
