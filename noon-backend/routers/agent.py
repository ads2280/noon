"""Agent router for calendar operations."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
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
    from noon_agent.gcal_auth import get_calendar_service
    from noon_agent.gcal_wrapper import get_event_details, read_calendar_events
except ImportError as e:
    logging.error(f"Failed to import agent modules: {e}")
    raise

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


def _extract_intent_category(text: str, tool: str) -> str | None:
    """Extract intent category from user text and tool."""
    text_lower = text.lower()
    
    if tool == "create":
        if any(word in text_lower for word in ["meeting", "appointment", "call"]):
            return "schedule_meeting"
        elif any(word in text_lower for word in ["coffee", "lunch", "dinner"]):
            return "schedule_social"
        return "create_event"
    elif tool == "read" or tool == "schedule":
        return "view_calendar"
    elif tool == "search":
        return "find_event"
    elif tool == "update":
        return "modify_event"
    elif tool == "delete":
        return "cancel_event"
    
    return None


def _extract_entities(result_data: dict | None) -> dict:
    """Extract entities (people, times, locations) from result data."""
    entities = {}
    
    # Extract from result_data if available
    if result_data:
        if "attendees" in result_data:
            entities["people"] = result_data.get("attendees", [])
        if "location" in result_data:
            entities["location"] = result_data.get("location")
        if "start" in result_data:
            entities["time"] = result_data.get("start")
    
    return entities


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

        # Log agent request details (enhanced logging)
        try:
            from services.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            # Extract intent and entities (simplified - can be enhanced with NLP)
            intent_category = _extract_intent_category(payload.text, tool_name)
            entities = _extract_entities(result_data)
            
            # Update request log with agent details
            supabase.table("request_logs").update({
                "agent_action": tool_name,
                "agent_tool": tool_name,
                "agent_success": success,
                "agent_summary": summary[:500],  # Truncate if too long
                "intent_category": intent_category,
                "entities": entities,
            }).eq("user_id", current_user.id).order("created_at", desc=True).limit(1).execute()
        except Exception as e:
            logger.debug(f"Failed to update request log with agent details: {e}")

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


@router.post("/event", response_model=agent_schema.GetEventResponse)
async def get_event_details_with_schedule(
    payload: agent_schema.GetEventRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> agent_schema.GetEventResponse:
    """
    Get full event details by event ID and calendar ID.
    
    Note: Google Calendar event IDs are unique per calendar, not globally unique.
    Therefore, both event_id and calendar_id are required to uniquely identify an event.
    
    If calendar_id is not provided, the function will search across all user calendars
    to find the event (less efficient but more convenient).
    
    Also retrieves the day's schedule for the event's date.
    
    Returns:
    - event: Full event details
    - day_schedule: All events for that day
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

        # Get calendar service
        service = get_calendar_service(access_token)

        # Determine which calendar to search
        calendar_id = payload.calendar_id
        all_calendar_ids = user_context.get("all_calendar_ids", [])
        
        # If calendar_id not provided, search across all calendars
        if not calendar_id or calendar_id == "primary":
            # Try primary calendar first
            primary_calendar_id = user_context.get("primary_calendar_id", "primary")
            event_result = get_event_details(
                service=service,
                event_id=payload.event_id,
                calendar_id=primary_calendar_id,
            )
            
            # If not found in primary, search other calendars
            if event_result.get("status") != "success" and all_calendar_ids:
                for cal_id in all_calendar_ids:
                    if cal_id == primary_calendar_id:
                        continue  # Already tried
                    event_result = get_event_details(
                        service=service,
                        event_id=payload.event_id,
                        calendar_id=cal_id,
                    )
                    if event_result.get("status") == "success":
                        calendar_id = cal_id
                        break
        else:
            # Use provided calendar_id
            event_result = get_event_details(
                service=service,
                event_id=payload.event_id,
                calendar_id=calendar_id,
            )

        if event_result.get("status") != "success":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event not found: {event_result.get('error', 'Unknown error')}. Note: Event IDs are unique per calendar, so the event_id must exist in the specified calendar_id.",
            )

        event = event_result
        # Update calendar_id in event if we found it in a different calendar
        if calendar_id and event.get("calendar_id") != calendar_id:
            event["calendar_id"] = calendar_id

        # Parse event start time to get the day
        start_time_str = event.get("start", "")
        if not start_time_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event has no start time",
            )

        # Parse the start time to extract the date
        try:
            # Handle both dateTime and date formats
            # Extract just the date part (YYYY-MM-DD)
            if "T" in start_time_str:
                date_part = start_time_str.split("T")[0]
            else:
                date_part = start_time_str
            
            # Parse date components
            year, month, day = map(int, date_part.split("-")[:3])
            event_start = datetime(year, month, day)
        except (ValueError, IndexError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event start time format: {start_time_str}",
            ) from e

        # Calculate day boundaries (start and end of the event's day)
        day_start = event_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Get all events for that day (use the calendar_id where we found the event)
        final_calendar_id = event.get("calendar_id", payload.calendar_id or "primary")
        schedule_result = read_calendar_events(
            service=service,
            calendar_id=final_calendar_id,
            time_min=day_start,
            time_max=day_end,
            max_results=500,  # High limit to get all events for the day
        )

        day_schedule = schedule_result if schedule_result.get("status") == "success" else {
            "status": "error",
            "error": schedule_result.get("error", "Unknown error"),
            "events": [],
            "count": 0,
        }

        return agent_schema.GetEventResponse(
            event=event,
            day_schedule=day_schedule,
            success=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting event details for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get event details: {str(e)}",
        ) from e
