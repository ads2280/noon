"""
FastAPI application for voice-to-natural-language transcription using Deepgram.
Provides both REST API and WebSocket endpoints for audio transcription with
optional custom vocabulary support.
"""
import os
import io
import asyncio
from pathlib import Path
from typing import Optional, List, Tuple
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel
from dotenv import load_dotenv
import logging
import json
import httpx
import aiohttp

# Load .env file from noon-v2nl directory
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Noon Voice-to-Natural-Language API (Deepgram)",
    description="""
    Microservice that takes in audio and returns natural language strings using Deepgram transcription.
    
    Endpoints:
    - REST: POST /oai/transcribe
    - WebSocket: WS /oai/stream
    """,
    version="0.2.0"
)

# Deepgram configuration (only API key from environment)
DG_API_KEY = os.getenv("DEEPGRAM_API_KEY")
# Fixed defaults for English
DG_MODEL = "nova-3"
DG_LANGUAGE = "en-US"
DG_SMART_FORMAT = True
DG_PUNCTUATE = True

if not DG_API_KEY:
    logger.warning("DEEPGRAM_API_KEY not found in environment variables")


class TranscriptionResponse(BaseModel):
    """Response model for transcription endpoint"""
    text: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "noon-v2nl",
        "provider": "deepgram",
        "endpoints": {
            "rest": "/oai/transcribe",
            "websocket": "/oai/stream"
        }
    }


def _parse_vocabulary(vocab_str: Optional[str]) -> List[str]:
    if not vocab_str:
        return []
    parts = [p.strip() for p in vocab_str.split(",")]
    return [p for p in parts if p]


def _guess_mime_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mime_types = {
        ".mp3": "audio/mpeg",
        ".mp4": "audio/mp4",
        ".mpeg": "audio/mpeg",
        ".mpga": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".opus": "audio/opus",
        ".aac": "audio/aac",
        ".mp2": "audio/mpeg",
        ".3gp": "audio/3gpp",
    }
    return mime_types.get(ext, "application/octet-stream")


def _extract_transcript_from_deepgram(json_payload: dict) -> str:
    try:
        channels = json_payload.get("results", {}).get("channels", [])
        if not channels:
            return ""
        alts = channels[0].get("alternatives", [])
        if not alts:
            return ""
        return alts[0].get("transcript", "") or ""
    except Exception:
        return ""


@app.post("/oai/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    vocabulary: Optional[str] = Query(None, description="Comma-separated custom vocabulary terms"),
):
    """
    Transcribe an audio file using Deepgram's prerecorded API.
    Returns plain text in the response model.
    """
    if not DG_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Deepgram API key not configured. Please set DEEPGRAM_API_KEY."
        )
    
    try:
        # Read the uploaded file
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Validate file size (25 MB limit to mirror prior behavior)
        if len(audio_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File size exceeds 25 MB limit")
        
        filename = file.filename or "audio.wav"
        mime_type = file.content_type or _guess_mime_type(filename)
        
        # Build query params
        vocab_terms = _parse_vocabulary(vocabulary)
        params: List[Tuple[str, str]] = [
            ("model", DG_MODEL),
            ("smart_format", "true" if DG_SMART_FORMAT else "false"),
            ("punctuate", "true" if DG_PUNCTUATE else "false"),
            ("language", DG_LANGUAGE),
        ]
        for term in vocab_terms:
            # Deepgram supports repeating keywords params
            params.append(("keywords", term))
        
        headers = {
            "Authorization": f"Token {DG_API_KEY}",
            "Content-Type": mime_type,
        }
        
        logger.info(f"Deepgram prerecord transcription start: {filename}, {len(audio_bytes)} bytes")
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params=params,
                headers=headers,
                content=audio_bytes,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            payload = resp.json()
        
        text = _extract_transcript_from_deepgram(payload)
        logger.info("Deepgram prerecord transcription completed")
        return TranscriptionResponse(text=text)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio with Deepgram: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")


@app.websocket("/oai/stream")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint that proxies audio to Deepgram Live and streams back
    partial and final transcripts.
    
    Client contract:
    - Send binary messages with audio bytes (e.g. WAV chunks)
    - When done sending audio, send a text JSON: {"action":"transcribe", "model": "...", "language": "...", "vocabulary": "term1,term2"}
    - Server will emit:
        { "type": "transcription_delta", "text": "<partial text>" } as partials arrive
        { "type": "transcription_complete", "text": "<final text>" } when finished
    """
    await websocket.accept()
    
    if not DG_API_KEY:
        await websocket.send_json({
            "error": "Deepgram API key not configured. Please set DEEPGRAM_API_KEY."
        })
        await websocket.close()
        return
    
    # Will collect optional start config and any early audio bytes
    start_vocab: List[str] = []
    buffered_chunks: List[bytes] = []
    dg_ws = None
    final_text = ""
    partial_text_last_sent = ""
    upstream_closed = False
    
    from urllib.parse import urlencode
    dg_url_base = "wss://api.deepgram.com/v1/listen"
    
    # Wait for either a start command (with vocabulary) or first audio bytes
    try:
        first_msg = await asyncio.wait_for(websocket.receive(), timeout=10.0)
    except asyncio.TimeoutError:
        first_msg = None
    
    if first_msg:
        if "text" in first_msg:
            try:
                data = json.loads(first_msg["text"])
                if data.get("action") == "start":
                    start_vocab = _parse_vocabulary(data.get("vocabulary"))
                # else ignore unknown text and continue with defaults
            except json.JSONDecodeError:
                pass
        elif "bytes" in first_msg:
            buffered_chunks.append(first_msg["bytes"])
    
    # Build Deepgram URL with selected options and optional vocabulary
    query_params: List[Tuple[str, str]] = [
        ("model", DG_MODEL),
        ("smart_format", "true" if DG_SMART_FORMAT else "false"),
        ("punctuate", "true" if DG_PUNCTUATE else "false"),
        ("language", DG_LANGUAGE),
    ]
    for term in start_vocab:
        query_params.append(("keywords", term))
    dg_url = f"{dg_url_base}?{urlencode(query_params, doseq=True)}"
    
    # Forwarding functions are defined within the Deepgram connection block below
    
    async def forward_deepgram_to_client():
        nonlocal final_text, partial_text_last_sent, dg_ws
        try:
            async for message in dg_ws:
                # aiohttp returns WSMessage objects
                if message.type == aiohttp.WSMsgType.BINARY:
                    continue
                if message.type == aiohttp.WSMsgType.TEXT:
                    try:
                        payload = json.loads(message.data)
                    except Exception:
                        continue
                    if payload.get("type") == "Results":
                        results = payload.get("channel", {}).get("alternatives", [])
                        if not results:
                            continue
                        transcript = results[0].get("transcript", "")
                        if not transcript:
                            continue
                        if transcript != partial_text_last_sent:
                            partial_text_last_sent = transcript
                            await websocket.send_json({
                                "type": "transcription_delta",
                                "text": transcript
                            })
                        if payload.get("is_final"):
                            final_text = transcript
                elif message.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except Exception as e:
            logger.error(f"Error receiving Deepgram messages: {e}", exc_info=True)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                dg_url,
                headers={"Authorization": f"Token {DG_API_KEY}"},
                heartbeat=20
            ) as dg_ws_conn:
                dg_ws = dg_ws_conn

                async def _send_close_stream():
                    try:
                        await dg_ws.send_str(json.dumps({"type": "CloseStream"}))
                    except:
                        pass

                async def forward_client_to_deepgram():
                    nonlocal upstream_closed, dg_ws
                    try:
                        for chunk in buffered_chunks:
                            await dg_ws.send_bytes(chunk)
                        while True:
                            data = await websocket.receive()
                            if "bytes" in data:
                                await dg_ws.send_bytes(data["bytes"])
                            elif "text" in data:
                                try:
                                    command = json.loads(data["text"])
                                except json.JSONDecodeError:
                                    continue
                                action = command.get("action")
                                if action == "transcribe":
                                    await _send_close_stream()
                                    upstream_closed = True
                                elif action == "start":
                                    pass
                                elif action == "reset":
                                    pass
                    except WebSocketDisconnect:
                        upstream_closed = True
                        await _send_close_stream()
                    except Exception as e:
                        upstream_closed = True
                        logger.error(f"Error forwarding client audio to Deepgram: {e}", exc_info=True)
                        await _send_close_stream()

                to_dg = asyncio.create_task(forward_client_to_deepgram())
                from_dg = asyncio.create_task(forward_deepgram_to_client())
                await to_dg
                try:
                    await asyncio.wait_for(from_dg, timeout=10.0)
                except asyncio.TimeoutError:
                    pass
                await websocket.send_json({
                    "type": "transcription_complete",
                    "text": final_text or partial_text_last_sent
                })
    except Exception as e:
        logger.error(f"Deepgram live websocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"error": f"Deepgram live error: {str(e)}"})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

