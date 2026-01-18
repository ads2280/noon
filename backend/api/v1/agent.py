"""Agent endpoint for invoking the LangGraph calendar agent."""

import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Body
from pydantic import BaseModel
from langgraph_sdk import get_client

# Add parent directory to path to import from agent package
_parent_dir = Path(__file__).parent.parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

# Import schemas - agent/__init__.py now uses lazy imports, so importing
# agent.schemas.agent_response won't trigger main import
from agent.schemas.agent_response import (
    AgentResponse,
    ErrorResponse,
    ShowEventResponse,
    ShowScheduleResponse,
    CreateEventResponse,
    UpdateEventResponse,
    DeleteEventResponse,
    NoActionResponse,
)
from pydantic import ValidationError
from schemas.user import AuthenticatedUser
from core.dependencies import get_current_user
from core.config import get_settings
from core.timing_logger import log_step, log_start
from domains.transcription.service import TranscriptionService
from services import agent_calendar_service
from db.session import get_service_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# Initialize transcription service
transcription_service = TranscriptionService()


class AgentActionRequest(BaseModel):
    """Request model for agent action endpoint."""
    query: str


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Transcribe an audio file to text using Deepgram.
    
    Returns the transcribed text as JSON.
    """
    endpoint_start = time.time()
    log_start("backend.api.transcribe", details=f"user_id={current_user.id} filename={file.filename}")
    try:
        # Validate file
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Transcribe audio file
        try:
            # Reset file pointer to beginning in case it was read already
            await file.seek(0)
            transcribe_start = time.time()
            transcribed_text = await transcription_service.transcribe(
                file=file.file, filename=file.filename, mime_type=file.content_type
            )
            transcribe_duration = time.time() - transcribe_start
            log_step("backend.api.transcribe.transcription_service", transcribe_duration)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Transcription error: {str(e)}"
            )
        except Exception as e:
            # Log full error details for debugging (verbose internal logging)
            logger.error(
                f"Transcription failed user_id={current_user.id} file={file.filename}: {e}",
                exc_info=True,
            )
            # Return brief, user-friendly message (not technical details)
            raise HTTPException(
                status_code=500, detail="An error occurred while transcribing audio. Please try again."
            )

        if not transcribed_text or not transcribed_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Transcription resulted in empty text.",
            )

        endpoint_duration = time.time() - endpoint_start
        log_step("backend.api.transcribe", endpoint_duration, details=f"text_length={len(transcribed_text)}")
        return {"text": transcribed_text}

    except HTTPException:
        raise
    except Exception as e:
        # Log full error details for debugging (verbose internal logging)
        logger.error(
            f"Transcription endpoint failed user_id={current_user.id}: {e}",
            exc_info=True,
        )
        # Return brief, user-friendly message (not technical details)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while transcribing audio. Please try again."
        )


@router.post("/action")
async def agent_action(
    request: Request,
    body: AgentActionRequest = Body(..., description="Text query to process"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Invoke the LangGraph calendar agent with a text query.

    The text query is passed to the agent which will classify intent and extract
    metadata for calendar operations.
    """
    endpoint_start = time.time()
    query_text = body.query
    log_start("backend.api.action", details=f"user_id={current_user.id} query_length={len(query_text)}")
    try:
        # Extract Supabase access token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authentication token",
            )
        supabase_access_token = auth_header.replace("Bearer ", "", 1)

        # Prepare auth data with Supabase token
        auth = {
            "user_id": current_user.id,
            "supabase_access_token": supabase_access_token,
        }

        # Validate query text
        if not query_text or not query_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Query text is required and cannot be empty.",
            )

        # Create LangGraph SDK client and invoke agent
        settings = get_settings()

        parsed_url = urlparse(settings.langgraph_agent_url)
        is_local_agent = parsed_url.hostname in {"localhost", "127.0.0.1"}

        api_key = settings.langsmith_api_key or settings.langgraph_api_key

        if api_key is None and not is_local_agent:
            logger.error(
                f"LangGraph agent API key is missing for remote agent URL user_id={current_user.id}"
            )
            raise HTTPException(
                status_code=500,
                detail="Agent service is not configured with LangSmith authentication credentials."
            )

        client = get_client(
            url=settings.langgraph_agent_url,
            api_key=api_key,
        )

        # Get user timezone from users table
        timezone_start = time.time()
        supabase_client = get_service_client()
        user_timezone = None
        try:
            user_result = (
                supabase_client.table("users")
                .select("timezone")
                .eq("id", current_user.id)
                .single()
                .execute()
            )
            
            if user_result.data:
                user_timezone = user_result.data.get("timezone")
            else:
                logger.error(f"No user data returned user_id={current_user.id}")
            
            timezone_duration = time.time() - timezone_start
            log_step("backend.api.action.get_timezone", timezone_duration)
                
        except Exception as e:
            logger.error(
                f"Failed to get user timezone user_id={current_user.id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail="An error occurred while retrieving your timezone settings. Please try again."
            )
        
        # Validate timezone is set and not default 'UTC'
        if not user_timezone or user_timezone.strip() == "":
            logger.error(f"User timezone not configured user_id={current_user.id}")
            raise HTTPException(
                status_code=400,
                detail="User timezone is not configured. Please set your timezone in your account settings."
            )
        
        if user_timezone.upper() == "UTC":
            raise HTTPException(
                status_code=400,
                detail="User timezone is not configured. Please set your timezone in your account settings."
            )
        
        # Validate timezone is a valid IANA timezone
        current_utc = datetime.now(timezone.utc)
        try:
            user_tz = ZoneInfo(user_timezone)
            current_user_time = current_utc.astimezone(user_tz)
            current_time_str = current_user_time.isoformat()
            current_day_of_week = current_user_time.strftime("%A")  # Full day name
        except Exception as e:
            logger.error(
                f"Invalid timezone user_id={current_user.id} timezone={user_timezone}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timezone configuration: {user_timezone}. Please set a valid timezone in your account settings."
            )

        input_state = {
            "query": query_text,
            "auth": auth,
            "success": False,
            "type": None,
            "metadata": {},
            "messages": [],
            "tool_results": {},
            "terminated": False,
            "current_time": current_time_str,
            "timezone": user_timezone,
            "current_day_of_week": current_day_of_week,
        }

        logger.info(
            f"Invoking agent user_id={current_user.id} query_length={len(query_text)}"
        )

        # Invoke and wait for completion
        langgraph_start = time.time()
        result = await client.runs.wait(
            thread_id=None,
            assistant_id="agent",
            input=input_state,
        )
        langgraph_duration = time.time() - langgraph_start
        log_step("backend.api.action.langgraph_invoke", langgraph_duration, details=f"response_type={result.get('type')}")

        logger.info(
            f"Agent completed user_id={current_user.id} "
            f"type={result.get('type')} success={result.get('success')}"
        )

        # Validate and parse agent response using Pydantic models
        parse_start = time.time()
        try:
            if "message" in result:
                # Error response
                error_response = ErrorResponse.model_validate(result)
                parse_duration = time.time() - parse_start
                log_step("backend.api.action.parse_response", parse_duration, details="result=error")
                endpoint_duration = time.time() - endpoint_start
                log_step("backend.api.action", endpoint_duration)
                return error_response.model_dump()
            elif "type" in result:
                # Success response - parse based on type
                response_type = result.get("type")
                if response_type == "show-event":
                    response = ShowEventResponse.model_validate(result)
                elif response_type == "show-schedule":
                    response = ShowScheduleResponse.model_validate(result)
                elif response_type == "create-event":
                    response = CreateEventResponse.model_validate(result)
                elif response_type == "update-event":
                    response = UpdateEventResponse.model_validate(result)
                elif response_type == "delete-event":
                    response = DeleteEventResponse.model_validate(result)
                elif response_type == "no-action":
                    response = NoActionResponse.model_validate(result)
                else:
                    logger.warning(
                        f"Unknown response type user_id={current_user.id} type={response_type}"
                    )
                    error_response = ErrorResponse(
                        message=f"Unknown response type from agent: {response_type}"
                    )
                    parse_duration = time.time() - parse_start
                    log_step("backend.api.action.parse_response", parse_duration, details=f"result=unknown_type type={response_type}")
                    endpoint_duration = time.time() - endpoint_start
                    log_step("backend.api.action", endpoint_duration)
                    return error_response.model_dump()
                parse_duration = time.time() - parse_start
                log_step("backend.api.action.parse_response", parse_duration, details=f"result=success type={response_type}")
                endpoint_duration = time.time() - endpoint_start
                log_step("backend.api.action", endpoint_duration)
                return response.model_dump()
            else:
                # Fallback for unexpected responses - treat as error
                # This is an agent mistake, not a user error
                # Log full details for debugging (verbose internal logging)
                logger.warning(
                    f"Unexpected result format user_id={current_user.id} "
                    f"keys={list(result.keys())}"
                )
                # Return brief, user-friendly message (not technical details)
                error_response = ErrorResponse(
                    message="Agent failed to handle request precisely. Please try rephrasing your request."
                )
                parse_duration = time.time() - parse_start
                log_step("backend.api.action.parse_response", parse_duration, details="result=unexpected_format")
                endpoint_duration = time.time() - endpoint_start
                log_step("backend.api.action", endpoint_duration)
                return error_response.model_dump()
        except ValidationError as e:
            # This is an agent mistake (invalid response format), not a user error
            # Log full details for debugging (verbose internal logging)
            logger.error(
                f"Response validation failed user_id={current_user.id}: {e}",
                exc_info=True,
            )
            # Return brief, user-friendly message (not technical details)
            error_response = ErrorResponse(
                message="Agent failed to handle request precisely. Please try rephrasing your request."
            )
            endpoint_duration = time.time() - endpoint_start
            log_step("backend.api.action", endpoint_duration, details="result=validation_error")
            return error_response.model_dump()

    except HTTPException:
        endpoint_duration = time.time() - endpoint_start
        log_step("backend.api.action", endpoint_duration, details="result=http_exception")
        raise
    except Exception as e:
        # Log full error details for debugging (verbose internal logging)
        logger.error(
            f"Agent invocation failed user_id={current_user.id}: {e}",
            exc_info=True,
        )
        # Return brief, user-friendly message (not technical details)
        endpoint_duration = time.time() - endpoint_start
        log_step("backend.api.action", endpoint_duration, details=f"error={str(e)[:80]}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request. Please try again."
        )
