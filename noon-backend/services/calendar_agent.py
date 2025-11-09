"""Service wrapper around the Noon calendar agent."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _import_agent_components():
    """Ensure the noon-agent package is importable and return required symbols."""

    agent_root = Path(__file__).resolve().parents[2] / "noon-agent"
    if not agent_root.exists():
        raise ImportError(f"Could not locate noon-agent at {agent_root}")
    agent_path = str(agent_root)
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)

    try:
        from noon_agent.main import graph  # type: ignore
        from noon_agent.db_context import load_user_context_from_db  # type: ignore
    except ImportError as exc:  # pragma: no cover - startup failure
        raise ImportError("Failed to import noon-agent modules") from exc

    return graph, load_user_context_from_db


class CalendarAgentError(RuntimeError):
    """Base error raised when the calendar agent invocation fails."""


class CalendarAgentUserError(CalendarAgentError):
    """Raised when a user-specific precondition fails (e.g., missing token)."""


class CalendarAgentService:
    """Encapsulates invocation of the Noon LangGraph calendar agent."""

    def __init__(
        self,
        *,
        graph: Optional[Any] = None,
        load_user_context: Optional[Any] = None,
    ) -> None:
        if graph is None or load_user_context is None:
            default_graph, default_loader = _import_agent_components()
            graph = graph or default_graph
            load_user_context = load_user_context or default_loader

        self._graph = graph
        self._load_user_context = load_user_context

    def _build_agent_state(
        self, *, message: str, user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build the agent state object expected by noon-agent."""

        access_token = user_context.get("access_token")
        if not access_token:
            raise CalendarAgentUserError(
                "User has no Google Calendar access token. Please link your Google account first."
            )

        context = {
            "primary_calendar_id": user_context.get("primary_calendar_id", "primary"),
            "timezone": user_context.get("timezone", "UTC"),
            "all_calendar_ids": user_context.get("all_calendar_ids", []),
            "friends": user_context.get("friends", []),
        }

        state: State = {
            "messages": message,
            "auth_token": access_token,
            "context": context,
        }
        return state

    def _load_context(self, user_id: str) -> Dict[str, Any]:
        try:
            return self._load_user_context(user_id)
        except ValueError as exc:
            raise CalendarAgentUserError(str(exc)) from exc

    def chat(self, *, user_id: str, message: str) -> Dict[str, Any]:
        """
        Invoke the calendar agent for the given user and message.

        Returns:
            Dict with tool, summary, result, success keys to match API schema.
        """

        if not message:
            raise CalendarAgentUserError("Message text cannot be empty.")

        user_context = self._load_context(user_id)
        state = self._build_agent_state(message=message, user_context=user_context)

        logger.info("CALENDAR_AGENT_SERVICE: invoking agent graph for user %s", user_id)
        try:
            full_result = self._graph.invoke(state)
        except Exception as exc:
            logger.exception(
                "Calendar agent graph invocation failed for user %s", user_id
            )
            raise CalendarAgentError(f"Agent invocation failed: {exc}") from exc

        tool_name = full_result.get("action") or "read"
        summary = (
            full_result.get("response") or full_result.get("summary") or "No response"
        )
        success = full_result.get("success", True)

        return {
            "tool": tool_name,
            "summary": summary,
            "result": full_result.get("result_data"),
            "success": success,
        }


class _CalendarAgentServiceProxy:
    """Lazy loader that instantiates the real service on first use."""

    def __init__(self):
        self._service: CalendarAgentService | None = None

    def _ensure(self) -> CalendarAgentService:
        if self._service is None:
            self._service = CalendarAgentService()
        return self._service

    def __getattr__(self, item):
        return getattr(self._ensure(), item)


calendar_agent_service = _CalendarAgentServiceProxy()

__all__ = [
    "calendar_agent_service",
    "CalendarAgentService",
    "CalendarAgentError",
    "CalendarAgentUserError",
]
