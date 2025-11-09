"""
Test script for noon-v2nl transcription API.
Tests both REST and WebSocket endpoints with audio files from tests/clips/.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
import requests
import websockets
from typing import List

# Add parent directory to path to import from main if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
WS_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
CLIPS_DIR = Path(__file__).parent / "clips"
CHUNK_SIZE = 4096  # 4KB chunks for streaming

# Optional list of custom vocabulary terms to boost during transcription tests.
# Populate with strings (case-sensitive) e.g. ["Noon", "Deepgram", "AI"]
CUSTOM_VOCABULARY: List[str] = []


def get_vocab_string() -> str:
    """Convert the custom vocabulary list into a comma-separated string."""
    cleaned_terms = [term.strip() for term in CUSTOM_VOCABULARY if term.strip()]
    return ",".join(cleaned_terms)


def find_audio_files(directory: Path) -> List[Path]:
    """Find all audio files in the given directory.
    
    Finds common audio formats supported by Deepgram.
    Deepgram supports: mp3, mp4, mpeg, mpga, m4a, wav, webm, flac, ogg, opus, aac, mp2, 3gp
    """
    if not directory.exists():
        print(f"⚠️  Directory {directory} does not exist. Creating it...")
        directory.mkdir(parents=True, exist_ok=True)
        return []
    
    # Find all common audio formats supported by Deepgram
    audio_extensions = [
        "*.mp3", "*.mp4", "*.mpeg", "*.mpga", "*.m4a", "*.wav", "*.webm",
        "*.flac", "*.ogg", "*.opus", "*.aac", "*.mp2", "*.3gp"
    ]
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(directory.glob(ext))
    
    if not audio_files:
        print(f"⚠️  No audio files found in {directory}")
        print(f"   Common formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, flac, ogg, opus, aac, mp2, 3gp")
        print(f"   Please add audio files to {directory}")
    return sorted(audio_files)


def test_rest_endpoint(audio_file: Path) -> str:
    """
    Test the REST API endpoint /v1/transcriptions.
    
    Args:
        audio_file: Path to the audio file to transcribe
        
    Returns:
        Transcribed text
    """
    print(f"\n{'='*80}")
    print(f"📤 REST API Test: {audio_file.name}")
    print(f"{'='*80}")
    
    url = f"{BASE_URL}/v1/transcriptions"
    
    try:
        # Determine MIME type based on file extension
        # Deepgram supports all these formats
        ext = audio_file.suffix.lower()
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
            ".3gp": "audio/3gpp"
        }
        mime_type = mime_types.get(ext, "audio/mpeg")  # Default to mpeg
        
        with open(audio_file, "rb") as f:
            files = {"file": (audio_file.name, f, mime_type)}
            # Optional vocabulary (comma-separated) passed as argument if provided via custom list
            dg_vocab = get_vocab_string()
            data = {}
            if dg_vocab:
                data["vocabulary"] = dg_vocab
                print(f"   Using vocabulary: {dg_vocab}")
            
            print(f"   Uploading {audio_file.name} ({audio_file.stat().st_size / 1024:.1f} KB)...")
            response = requests.post(url, files=files, data=data, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                transcription = result.get("text", "")
                print(f"\n✅ REST Transcription Result:")
                print(f"{'─'*80}")
                print(f"{transcription}")
                print(f"{'─'*80}")
                return transcription
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   {response.text}")
                return ""
                
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Could not connect to {BASE_URL}")
        print(f"   Make sure the FastAPI server is running!")
        return ""
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return ""


async def test_websocket_endpoint(audio_file: Path) -> str:
    """
    Test the WebSocket endpoint /v1/transcriptions/stream.
    
    Args:
        audio_file: Path to the audio file to transcribe
        
    Returns:
        Full transcribed text
    """
    print(f"\n{'='*80}")
    print(f"🌐 WebSocket Stream Test: {audio_file.name}")
    print(f"{'='*80}")
    
    ws_url = f"{WS_URL}/v1/transcriptions/stream"
    full_transcription = ""
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"   Connected to WebSocket: {ws_url}")
            
            # Send start command with optional vocabulary BEFORE streaming
            start_cmd = {"action": "start"}
            dg_vocab = get_vocab_string()
            if dg_vocab:
                start_cmd["vocabulary"] = dg_vocab
                print(f"   Using vocabulary: {dg_vocab}")
            await websocket.send(json.dumps(start_cmd))
            
            # Read and send audio file in chunks
            print(f"   Streaming audio chunks...")
            total_sent = 0
            
            with open(audio_file, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    await websocket.send(chunk)
                    total_sent += len(chunk)
                    print(f"   Sent {total_sent / 1024:.1f} KB", end="\r")
            
            print(f"\n   Total sent: {total_sent / 1024:.1f} KB")
            
            # Send transcribe command (end-of-stream signal)
            command = {
                "action": "transcribe",
                "filename": audio_file.name
            }
            print(f"   Sending transcribe command...")
            await websocket.send(json.dumps(command))
            
            # Receive streaming transcription
            print(f"\n📝 Streaming Transcription (building in real-time):")
            print(f"{'─'*80}")
            print()  # Start on a new line for the transcription
            
            transcription_parts = []
            while True:
                try:
                    # Set a timeout for receiving messages
                    message = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    
                    if isinstance(message, str):
                        data = json.loads(message)
                        
                        if data.get("type") == "transcription_delta":
                            delta_text = data.get("text", "")
                            transcription_parts.append(delta_text)
                            # Print each streamed delta on its own line for clarity
                            print(delta_text, flush=True)
                            
                        elif data.get("type") == "transcription_complete":
                            complete_text = data.get("text", "")
                            if complete_text:
                                full_transcription = complete_text
                            else:
                                # Fallback: use accumulated parts
                                full_transcription = "".join(transcription_parts)
                            # Add newline after the complete transcription
                            print()  # Newline after the streaming text
                            print(f"{'─'*80}")
                            print(f"✅ WebSocket Transcription Complete")
                            break
                            
                        elif "error" in data:
                            print()  # Newline before error
                            print(f"❌ Error: {data.get('error')}")
                            break
                            
                except asyncio.TimeoutError:
                    print()  # Newline after timeout
                    print(f"⚠️  Timeout waiting for response")
                    # Use accumulated parts if we have them
                    if transcription_parts:
                        full_transcription = "".join(transcription_parts)
                    break
                    
    except websockets.exceptions.InvalidURI:
        print(f"❌ Invalid WebSocket URL: {ws_url}")
        return ""
    except websockets.exceptions.ConnectionClosed:
        print(f"\n⚠️  WebSocket connection closed")
        # Use accumulated parts if we have them
        if transcription_parts:
            full_transcription = "".join(transcription_parts)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return ""
    
    return full_transcription


async def test_file(audio_file: Path):
    """Test both REST and WebSocket endpoints for a single audio file."""
    print(f"\n{'#'*80}")
    print(f"# Testing: {audio_file.name}")
    print(f"{'#'*80}")
    
    # Test REST endpoint
    rest_result = test_rest_endpoint(audio_file)
    
    # Wait a bit between tests
    await asyncio.sleep(1)
    
    # Test WebSocket endpoint
    ws_result = await test_websocket_endpoint(audio_file)
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 Summary for {audio_file.name}:")
    print(f"{'='*80}")
    print(f"REST API:     {'✅' if rest_result else '❌'} ({len(rest_result)} chars)")
    print(f"WebSocket:    {'✅' if ws_result else '❌'} ({len(ws_result)} chars)")
    
    if rest_result and ws_result:
        # Compare results with normalized whitespace
        def _normalize_text(s: str) -> str:
            return " ".join(s.split())
        rest_norm = _normalize_text(rest_result)
        ws_norm = _normalize_text(ws_result)
        if rest_norm == ws_norm:
            print(f"Comparison:   Results match (normalized)")
            print(f"REST final results: {rest_norm}")
            print(f"WS final results:   {ws_norm}")
        else:
            print(f"Comparison:   Results differ")
            print(f"REST final results: {rest_norm}")
            print(f"WS final results:   {ws_norm}")
    
    print(f"{'='*80}\n")


async def main():
    """Main test runner."""
    print(f"\n{'='*80}")
    print(f"🧪 Noon v2nl Transcription API Test Suite")
    print(f"{'='*80}")
    print(f"API Base URL: {BASE_URL}")
    print(f"WebSocket URL: {WS_URL}")
    print(f"Clips Directory: {CLIPS_DIR}")
    print(f"{'='*80}\n")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running\n")
        else:
            print(f"⚠️  Server returned status {response.status_code}\n")
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"   Please start the server with: python main.py")
        print(f"   or: uvicorn main:app --host 0.0.0.0 --port 8000\n")
        return
    except Exception as e:
        print(f"⚠️  Error checking server: {e}\n")
    
    # Find audio files
    audio_files = find_audio_files(CLIPS_DIR)
    
    if not audio_files:
        print(f"\n⚠️  No audio files to test. Exiting.")
        return
    
    print(f"📁 Found {len(audio_files)} audio file(s) to test:\n")
    for i, f in enumerate(audio_files, 1):
        size_kb = f.stat().st_size / 1024
        print(f"   {i}. {f.name} ({size_kb:.1f} KB)")
    print()
    
    # Test each file
    for audio_file in audio_files:
        await test_file(audio_file)
        # Small delay between files
        await asyncio.sleep(2)
    
    print(f"\n{'='*80}")
    print(f"✅ All tests completed!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())

