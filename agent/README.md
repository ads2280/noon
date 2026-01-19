# Agent

LangGraph agent that processes calendar queries using OpenAI.

## Running

1. Install dependencies:
   ```bash
   pip install -e .
   ```

2. Configure environment variables (see `.env.example` for required variables):
   - `OPENAI_API_KEY`: Required for LLM calls
   - `BACKEND_API_URL`: Backend API URL (default: `http://localhost:8000`)

3. Run the agent:
   ```bash
   langgraph dev
   ```

The agent will be available at the URL specified in your LangGraph configuration.
