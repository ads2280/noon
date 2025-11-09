"""Service for handling agent calendar operations."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import HTTPException

from schemas.agent_response import ErrorResponse
from schemas.confirm_action import (
    ConfirmActionRequest,
    CreateEventRequest,
    DeleteEventRequest,
    UpdateEventRequest,
)
from services import supabase_client
from google_calendar.utils.calendar_wrapper import (
    GoogleCalendarAPIError,
    GoogleCalendarCredentials,
    GoogleCalendarWrapper,
)

logger = logging.getLogger(__name__)


def get_calendar_wrapper_for_user(user_id: str) -> GoogleCalendarWrapper:
    """Get a GoogleCalendarWrapper instance for the user's first Google account."""
    accounts = supabase_client.list_google_accounts(user_id)
    if not accounts:
        raise HTTPException(
            status_code=400,
            detail="No Google account linked. Please connect a Google account first."
        )
    
    account = accounts[0]
    access_token = account.get("access_token")
    refresh_token = account.get("refresh_token")
    
    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Google account missing access or refresh token."
        )
    
    credentials = GoogleCalendarCredentials(
        access_token=access_token,
        refresh_token=refresh_token,
    )
    return GoogleCalendarWrapper(credentials)


async def confirm_calendar_action(
    user_id: str,
    payload: ConfirmActionRequest,
) -> Dict[str, Any]:
    """
    Confirm and execute a calendar action based on the agent's request.
    
    Handles write operations that require confirmation:
    - create-event: Create a new event
    - update-event: Update an existing event
    - delete-event: Delete an event
    """
    wrapper = get_calendar_wrapper_for_user(user_id)
    
    if isinstance(payload, CreateEventRequest):
        # Create a new event
        event_data = dict(payload.metadata)  # Make a copy to avoid mutating the original
        
        # Extract calendar_id from event_data or default to "primary"
        calendar_id = event_data.pop("calendar_id", event_data.pop("calendar-id", "primary"))
        
        try:
            created_event = await wrapper.create_event(
                calendar_id=calendar_id,
                event_data=event_data,
            )
            return {
                "success": "true",
                "request": "create-event",
                "metadata": created_event,
            }
        except GoogleCalendarAPIError as e:
            return ErrorResponse(
                success="false",
                message=f"Failed to create event: {str(e)}"
            ).model_dump()
    
    elif isinstance(payload, UpdateEventRequest):
        # Update an existing event
        metadata = payload.metadata
        event_id = metadata.event_id
        calendar_id = metadata.calendar_id
        
        # Extract event data (everything except event-id and calendar-id)
        event_data = {
            k: v for k, v in metadata.model_dump(by_alias=True).items()
            if k not in ("event-id", "calendar-id")
        }
        
        try:
            updated_event = await wrapper.update_event(
                calendar_id=calendar_id,
                event_id=event_id,
                event_data=event_data,
            )
            return {
                "success": "true",
                "request": "update-event",
                "metadata": {
                    "event-id": event_id,
                    "calendar-id": calendar_id,
                    **updated_event,
                }
            }
        except GoogleCalendarAPIError as e:
            if e.status_code == 404:
                return ErrorResponse(
                    success="false",
                    message=f"Event not found: {str(e)}"
                ).model_dump()
            return ErrorResponse(
                success="false",
                message=f"Failed to update event: {str(e)}"
            ).model_dump()
    
    elif isinstance(payload, DeleteEventRequest):
        # Delete an event
        metadata = payload.metadata
        try:
            await wrapper.delete_event(
                calendar_id=metadata.calendar_id,
                event_id=metadata.event_id,
            )
            return {
                "success": "true",
                "request": "delete-event",
                "metadata": {
                    "event-id": metadata.event_id,
                    "calendar-id": metadata.calendar_id,
                }
            }
        except GoogleCalendarAPIError as e:
            if e.status_code == 404:
                return ErrorResponse(
                    success="false",
                    message=f"Event not found: {str(e)}"
                ).model_dump()
            return ErrorResponse(
                success="false",
                message=f"Failed to delete event: {str(e)}"
            ).model_dump()
    
    else:
        return ErrorResponse(
            success="false",
            message=f"Unknown request type: {type(payload)}"
        ).model_dump()

