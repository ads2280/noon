"""Agent endpoint for invoking the LangGraph calendar agent."""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from langgraph_sdk import get_client

from schemas.user import AuthenticatedUser
from schemas.agent_response import AgentResponse
from dependencies import get_current_user
from services import supabase_client
from config import get_settings
from v2nl import TranscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# Initialize transcription service
transcription_service = TranscriptionService()


@router.post("/action", response_model=AgentResponse)
async def agent_action(
    file: UploadFile = File(..., description="Audio file to transcribe and process"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Invoke the LangGraph calendar agent with an audio file.

    The audio file is first transcribed using Deepgram, then the transcribed text
    is passed to the agent which will classify intent and extract metadata for calendar operations.
    """
    try:
        # Get user's Google OAuth tokens from Supabase
        accounts = supabase_client.list_google_accounts(current_user.id)
        if not accounts:
            raise HTTPException(
                status_code=400,
                detail="No Google account linked. Please connect a Google account first."
            )
        
        # Choose first account
        google_account = accounts[0]
        
        # Prepare auth data with Google tokens
        # The agent expects tokens in a nested structure
        auth = {
            "user_id": current_user.id,
            "google_tokens": {
                "access_token": google_account.get("access_token"),
                "refresh_token": google_account.get("refresh_token"),
                "expires_at": google_account.get("expires_at"),
            }
        }

        # Validate file
        if not file or not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file provided"
            )

        # Transcribe audio file
        logger.info(f"Transcribing audio file: {file.filename} for user {current_user.id}")
        try:
            # Reset file pointer to beginning in case it was read already
            await file.seek(0)
            transcribed_text = await transcription_service.transcribe(
                file=file.file,
                filename=file.filename,
                mime_type=file.content_type
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Transcription error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to transcribe audio: {str(e)}"
            )

        if not transcribed_text or not transcribed_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Transcription resulted in empty text. Please ensure the audio file contains speech."
            )

        logger.info(f"Transcription completed: {transcribed_text[:100]}...")


        # Create LangGraph SDK client and invoke agent
        settings = get_settings()
        client = get_client(url=settings.langgraph_agent_url)

        input_state = {
            "query": transcribed_text,
            "auth": auth,
            "success": False,
            "request": "no-action",
            "metadata": {}
        }

        logger.info(f"Invoking agent for user {current_user.id} with transcribed query: {transcribed_text[:50]}...")

        # Invoke and wait for completion
        result = await client.runs.wait(
            thread_id=None,
            assistant_id="agent",
            input=input_state,
        )

        logger.info(f"Agent completed. Request: {result.get('request')}, Success: {result.get('success')}")

        return {
            "success": result.get("success", False),
            "request": result.get("request", "no-action"),
            "metadata": result.get("metadata", {})
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent invocation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to invoke agent: {str(e)}"
        )
