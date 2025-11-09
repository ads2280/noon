"""Agent router for calendar operations."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import AuthenticatedUser, get_current_user
from schemas import agent as agent_schema

# Add noon-agent to path for imports
agent_path = Path(__file__).parent.parent.parent / "noon-agent"
if str(agent_path) not in sys.path:
    sys.path.insert(0, str(agent_path))

try:
    from noon_agent.main import State, graph
    from noon_agent.db_context import load_user_context_from_db
except ImportError as e:
    logging.error(f"Failed to import agent modules: {e}")
    raise

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=agent_schema.AgentChatResponse)
async def chat_with_agent(
    payload: agent_schema.AgentChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> agent_schema.AgentChatResponse:
    """
    Chat with the calendar agent.

    Accepts natural language input and returns structured JSON with:
    - tool: The action/tool that was called
    - summary: Human-readable summary
    - result: Full tool result (if available)
    - success: Whether the operation succeeded
    """
    try:
        # Load user context from database
        try:
            user_context = load_user_context_from_db(current_user.id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to load user context: {str(e)}",
            ) from e

        # Check if user has Google access token
        access_token = user_context.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has no Google Calendar access token. Please link your Google account first.",
            )

        # Prepare agent state
        agent_state: State = {
            "messages": payload.text,
            "auth_token": access_token,
            "context": {
                "primary_calendar_id": user_context.get(
                    "primary_calendar_id", "primary"
                ),
                "timezone": user_context.get("timezone", "UTC"),
                "all_calendar_ids": user_context.get("all_calendar_ids", []),
                "friends": user_context.get("friends", []),
            },
        }

        # Invoke the agent
        # Note: graph.invoke returns the full state, not just OutputState
        full_result = graph.invoke(agent_state)

        # Extract tool name from action
        tool_name = full_result.get("action", "read")
        if not tool_name:
            tool_name = "read"

        # Get summary from response or summary field
        summary = full_result.get("response") or full_result.get(
            "summary", "No response"
        )

        # Determine success
        success = full_result.get("success", True)

        # Extract result data from the agent execution
        result_data = full_result.get("result_data")

        return agent_schema.AgentChatResponse(
            tool=tool_name,
            summary=summary,
            result=result_data,
            success=success,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error invoking agent for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent invocation failed: {str(e)}",
        ) from e
