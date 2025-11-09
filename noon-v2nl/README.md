## v2nl (voice to natural language)

Microservice that takes in audio and returns natural language string using Deepgram transcription.

### Features

- **REST API Endpoint** (`/v1/transcriptions`): Transcribe audio files via POST request
- **WebSocket Endpoint** (`/v1/transcriptions/stream`): Stream audio chunks and receive transcription (final message)

### Setup

1. **Install dependencies:**

```bash
pip install -r requirements.txt
# or using uv
uv pip install -r requirements.txt
```

2. **Set environment variables:**

Create a `.env` file or export the Deepgram API key:

```bash
export DEEPGRAM_API_KEY=your_deepgram_api_key_here
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

### REST API Endpoint: `/v1/transcriptions`

**Method:** POST

**Content-Type:** multipart/form-data

**Parameters:**
- `file` (required): Audio file to transcribe
  - Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, flac, ogg, opus, aac, mp2, 3gp
  - Max size: 25 MB
- `vocabulary` (optional): Comma-separated custom vocabulary terms to improve transcription accuracy

**Example using curl:**

```bash
curl -X POST "http://localhost:8000/v1/transcriptions" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@audio.mp3" \
  -F "vocabulary=term1,term2,term3"
```

**Example using Python:**

```python
import requests

url = "http://localhost:8000/v1/transcriptions"
files = {"file": open("audio.mp3", "rb")}
data = {
    "vocabulary": "term1,term2,term3"  # Optional
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

### WebSocket Endpoint: `/v1/transcriptions/stream`

**URL:** `ws://localhost:8000/v1/transcriptions/stream`

**Protocol:**

1. **Optionally send start command** with vocabulary as JSON text message:
   - `{"action": "start", "vocabulary": "term1,term2,term3"}` - Configure vocabulary before streaming
2. **Send audio chunks** as binary messages (bytes)
3. **Send control commands** as JSON text messages:
   - `{"action": "transcribe", "filename": "your_file.wav"}` - Transcribe accumulated audio
   - `{"action": "reset"}` - Reset accumulated audio chunks

**Example using Python:**

```python
import asyncio
import websockets
import json

async def transcribe_audio():
    uri = "ws://localhost:8000/v1/transcriptions/stream"
    
    async with websockets.connect(uri) as websocket:
        # Optionally send start command with vocabulary
        start_cmd = {
            "action": "start",
            "vocabulary": "term1,term2,term3"  # Optional
        }
        await websocket.send(json.dumps(start_cmd))
        
        # Send audio chunks (example)
        with open("audio.mp3", "rb") as f:
            chunk = f.read(1024)
            while chunk:
                await websocket.send(chunk)
                chunk = f.read(1024)
        
        # Request transcription
        command = {
            "action": "transcribe",
            "filename": "audio.wav"
        }
        await websocket.send(json.dumps(command))
        
        # Receive transcription results
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "transcription_delta":
                print(f"Partial: {data.get('text')}")
            elif data.get("type") == "transcription_complete":
                print(f"\n\nFull text: {data.get('text')}")
                break

asyncio.run(transcribe_audio())
```

**WebSocket Messages:**

**From client:**
- Binary: Audio chunks (bytes)
- Text: JSON control commands

**From server:**
- `{"type": "transcription_delta", "text": "..."}` - Partial transcription (streamed in real-time)
- `{"type": "transcription_complete", "text": "..."}` - Complete transcription
- `{"error": "..."}` - Error message

### Configuration

The service uses Deepgram's `nova-3` model with the following defaults:
- Language: `en-US`
- Smart formatting: Enabled
- Punctuation: Enabled

### Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `413`: File too large (>25 MB)
- `500`: Server error (check logs for details)

### Notes

- Audio files are limited to 25 MB
- For longer audio files, consider splitting them into chunks
- The WebSocket endpoint streams partial transcriptions in real-time as `transcription_delta` messages
- Include the original `filename` in the transcribe command to preserve the correct file extension (improves decoding reliability)
- Custom vocabulary terms can be provided to improve accuracy for domain-specific terminology
