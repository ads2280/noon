"""Backend HTTP client for calendar operations.

Makes HTTP requests to backend API endpoints for real Google Calendar data.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import httpx

from agent.calendar_client import CalendarClient

logger = logging.getLogger(__name__)


class BackendClient(CalendarClient):
    """
    HTTP client implementation that calls backend API endpoints.
    
    Uses Supabase JWT token from auth dict for authentication.
    """
    
    def __init__(self):
        """Initialize backend client with base URL from environment."""
        self.base_url = os.getenv("BACKEND_API_URL", "http://localhost:8000")
        # Remove trailing slash if present
        self.base_url = self.base_url.rstrip("/")
        self.timeout = 30.0  # 30 second timeout for API calls
        
    def _get_auth_token(self, auth: Optional[Dict[str, Any]]) -> str:
        """
        Extract Supabase access token from auth dict.
        
        Args:
            auth: Authentication dict with supabase_access_token
            
        Returns:
            Access token string
            
        Raises:
            ValueError: If auth or token is missing
        """
        if not auth:
            raise ValueError("Authentication required for backend API calls")
        token = auth.get("supabase_access_token")
        if not token:
            raise ValueError("supabase_access_token missing from auth dict")
        return token
    
    async def _make_request(
        self,
        method: str,
        path: str,
        auth: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to backend API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/api/v1/agent/calendars")
            auth: Authentication dict
            json_data: Optional JSON body
            params: Optional query parameters
            
        Returns:
            JSON response as dict
            
        Raises:
            httpx.HTTPError: If request fails
            ValueError: If auth is required but missing
        """
        token = self._get_auth_token(auth)
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data,
                    params=params,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Extract error message from response body
                # FastAPI returns JSON with "detail" field for HTTPException
                error_message = "Unknown error"
                try:
                    error_data = e.response.json()
                    if isinstance(error_data, dict) and "detail" in error_data:
                        error_message = str(error_data["detail"])
                    elif isinstance(error_data, dict) and "message" in error_data:
                        error_message = str(error_data["message"])
                    elif e.response.text:
                        error_message = e.response.text
                except Exception:
                    # If we can't parse the error, use response text or status code
                    error_message = e.response.text or f"Backend API error: {e.response.status_code}"
                
                logger.error(
                    f"Backend API error: {method} {url} - {e.response.status_code}: {error_message}"
                )
                raise ValueError(f"Backend API error: {error_message}") from e
            except httpx.RequestError as e:
                logger.error(f"Backend API request failed: {method} {url} - {str(e)}")
                raise ValueError(f"Backend API request failed: {str(e)}") from e
    
    async def read_schedule(
        self,
        start_time: str,
        end_time: str,
        auth: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Read events from schedule within a time window."""
        # Convert ISO datetime strings to date strings for the endpoint
        from datetime import datetime
        
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            start_date = start_dt.date().isoformat()
            end_date = end_dt.date().isoformat()
            
            # Get timezone from the datetime string if available, or default to UTC
            # The backend will need timezone - try to extract from start_time
            # For now, we'll let the backend handle timezone conversion
            # The user's timezone should be stored in their profile
            
            logger.info(f"Calling backend schedule endpoint: start_date={start_date}, end_date={end_date}")
            response = await self._make_request(
                method="POST",
                path="/api/v1/agent/calendars/schedule",
                auth=auth,
                json_data={
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
            
            events = response.get("events", [])
            logger.info(f"Backend returned {len(events)} events for date range {start_date} to {end_date}")
            if events:
                logger.info(f"Sample event: {events[0] if events else 'None'}")
            
            # Ensure all events have both id and calendar_id (required)
            formatted_events = []
            for event in events:
                if "id" not in event or "calendar_id" not in event:
                    logger.warning(f"Event missing required fields (id, calendar_id): {event}")
                    logger.warning(f"Event keys: {list(event.keys()) if isinstance(event, dict) else 'not a dict'}")
                    continue
                formatted_events.append({
                    "id": event["id"],
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "calendar_id": event["calendar_id"],
                    "calendar_name": event.get("calendar_name"),
                    "description": event.get("description"),
                    "location": event.get("location"),
                })
            logger.info(f"Formatted {len(formatted_events)} events after filtering")
            return formatted_events
            
        except Exception as e:
            logger.error(f"Failed to read schedule: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to read schedule: {str(e)}") from e
    
    async def search_events(
        self,
        keywords: str,
        start_time: str,
        end_time: str,
        auth: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for events matching keywords within a time window."""
        from datetime import datetime
        
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            
            # Format as ISO strings for the API
            response = await self._make_request(
                method="POST",
                path="/api/v1/agent/calendars/search",
                auth=auth,
                json_data={
                    "keywords": keywords,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
            
            events = response.get("events", [])
            # Ensure all events have both id and calendar_id (required)
            formatted_events = []
            for event in events:
                # Handle both event_id/id and calendar_id fields
                event_id = event.get("event_id") or event.get("id")
                calendar_id = event.get("calendar_id")
                
                if not event_id or not calendar_id:
                    logger.warning(f"Event missing required fields (id, calendar_id): {event}")
                    continue
                    
                formatted_events.append({
                    "id": event_id,
                    "summary": event.get("summary"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "calendar_id": calendar_id,
                    "calendar_name": event.get("calendar_name"),
                    "description": event.get("description"),
                    "location": event.get("location"),
                })
            return formatted_events
            
        except Exception as e:
            logger.error(f"Failed to search events: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to search events: {str(e)}") from e
    
    async def read_event(
        self,
        event_id: str,
        calendar_id: str,
        auth: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Read detailed information about a specific event."""
        try:
            response = await self._make_request(
                method="GET",
                path=f"/api/v1/agent/calendars/{calendar_id}/events/{event_id}",
                auth=auth,
            )
            
            # Ensure both id and calendar_id are present (required)
            event = response
            if "id" not in event:
                event["id"] = event_id
            if "calendar_id" not in event:
                event["calendar_id"] = calendar_id
                
            return event
            
        except Exception as e:
            logger.error(f"Failed to read event: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to read event: {str(e)}") from e
    
    async def list_calendars(
        self,
        auth: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """List all available calendars."""
        try:
            response = await self._make_request(
                method="GET",
                path="/api/v1/agent/calendars",
                auth=auth,
            )
            
            calendars = response.get("calendars", [])
            return calendars
            
        except Exception as e:
            logger.error(f"Failed to list calendars: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to list calendars: {str(e)}") from e
