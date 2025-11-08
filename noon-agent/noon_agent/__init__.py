"""LangGraph agent package for the Noon project."""

from .calendar_graph import build_calendar_graph, invoke_calendar_agent
from .calendar_state import CalendarAgentState, UserContext
from .config import AgentSettings, get_settings
from .gcal_auth import get_calendar_service, get_calendar_service_from_file

# Legacy exports for backwards compatibility
from .main import build_agent_graph, invoke_agent
from .schemas import AgentState

__all__ = [
    # Calendar agent (new)
    "build_calendar_graph",
    "invoke_calendar_agent",
    "CalendarAgentState",
    "UserContext",
    "get_calendar_service",
    "get_calendar_service_from_file",
    # Settings
    "AgentSettings",
    "get_settings",
    # Legacy (old)
    "build_agent_graph",
    "invoke_agent",
    "AgentState",
]
