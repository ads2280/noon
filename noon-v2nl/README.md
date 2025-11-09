## v2nl (voice to natural language)

Microservice that takes in audio and returns natural language string using OpenAI transcription.

### Features

- **REST API Endpoint** (`/oai/transcribe`): Transcribe audio files via POST request
- **WebSocket Endpoint** (`/oai/stream`): Stream audio chunks and receive transcription (final message)

### Setup

1. **Install dependencies:**

```bash
pip install -r requirements.txt
# or using uv
uv pip install -r requirements.txt
```

2. **Set environment variables:**

Create a `.env` file or export the OpenAI API key:

```bash
export OPENAI_API_KEY=your_openai_api_key_here
```

3. **Run the server:**

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### REST API Endpoint: `/oai/transcribe`

**Method:** POST

**Content-Type:** multipart/form-data

**Parameters:**
- `file` (required): Audio file to transcribe
  - Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm
  - Max size: 25 MB
- `model` (optional): Model to use
  - Options: `gpt-4o-transcribe` (default), `gpt-4o-mini-transcribe`, `whisper-1`
- `language` (optional): Language code (e.g., "en", "es", "fr")
- `prompt` (optional): Prompt to improve transcription quality
- `response_format` (optional): Response format
  - Options: `text` (default), `json`, `verbose_json`, `srt`, `vtt`
- `temperature` (optional): Temperature for the model (0.0 to 1.0, default: 0.0)

**Example using curl:**

```bash
curl -X POST "http://localhost:8000/oai/transcribe" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@audio.mp3" \
  -F "model=gpt-4o-transcribe" \
  -F "response_format=text"
```

**Example using Python:**

```python
import requests

url = "http://localhost:8000/oai/transcribe"
files = {"file": open("audio.mp3", "rb")}
data = {
    "model": "gpt-4o-transcribe",
    "response_format": "text"
}

response = requests.post(url, files=files, data=data)
print(response.json()["text"])
```

**Response:**

```json
{
  "text": "Transcribed text here..."
}
```

### WebSocket Endpoint: `/oai/stream`

**URL:** `ws://localhost:8000/oai/stream`

**Protocol:**

1. **Send audio chunks** as binary messages (bytes)
2. **Send control commands** as JSON text messages:
   - `{"action": "transcribe", "model": "gpt-4o-transcribe", "response_format": "text", "filename": "your_file.wav"}` - Transcribe accumulated audio
   - `{"action": "reset"}` - Reset accumulated audio chunks

**Example using Python:**

```python
import asyncio
import websockets
import json

async def transcribe_audio():
    uri = "ws://localhost:8000/oai/stream"
    
    async with websockets.connect(uri) as websocket:
        # Send audio chunks (example)
        with open("audio.mp3", "rb") as f:
            chunk = f.read(1024)
            while chunk:
                await websocket.send(chunk)
                chunk = f.read(1024)
        
        # Request transcription
        command = {
            "action": "transcribe",
            "model": "gpt-4o-transcribe",
            "response_format": "text",
            "filename": "audio.wav"
        }
        await websocket.send(json.dumps(command))
        
        # Receive transcription results
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "transcription_complete":
                print(f"\n\nFull text: {data.get('text')}")
                break

asyncio.run(transcribe_audio())
```

**WebSocket Messages:**

**From client:**
- Binary: Audio chunks (bytes)
- Text: JSON control commands

**From server:**
- `{"type": "transcription_delta", "text": "...", "full_text": "..."}` - Partial transcription
- `{"type": "transcription_complete", "text": "..."}` - Complete transcription
- `{"type": "reset_complete"}` - Reset confirmation
- `{"error": "..."}` - Error message

### Supported Models

- **gpt-4o-transcribe**: Higher quality transcription (recommended)
- **gpt-4o-mini-transcribe**: Faster, lower cost transcription
- **whisper-1**: Legacy Whisper model

### Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `413`: File too large (>25 MB)
- `500`: Server error (check logs for details)

### Notes

- Audio files are limited to 25 MB
- For longer audio files, consider splitting them into chunks
- The WebSocket endpoint accumulates audio chunks until a "transcribe" command is sent
- Include the original `filename` in the transcribe command to preserve the correct file extension (improves decoding reliability)
- This implementation sends the transcription as a final message; partial deltas are not streamed
