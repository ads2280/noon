# Backend

FastAPI backend API for authentication, transcription, and calendar services.

## Running

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Set up environment variables in `.env` (see `.env.example` for required variables)

3. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

The API will be available at `http://localhost:8000`
