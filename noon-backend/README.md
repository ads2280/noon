## Noon Backend

Lightweight FastAPI wrapper that forwards requests to the deployed LangGraph agent so you can emit traces from server-side code.

### Setup

```bash
cd noon-backend
uv sync             # or: uv pip install -e .
cp .env.example .env
```

Populate the `.env` file with:

- `LANGGRAPH_URL` – the public URL for your deployment (from LangGraph Cloud).
- `LANGSMITH_API_KEY` – API key with access to that deployment.
- `LANGGRAPH_AGENT_NAME` – graph name defined in `langgraph.json` (`noon-agent` by default).

### Run locally

```bash
uv run uvicorn main:app --reload --port 8080
```

### Send a message

```bash
curl -X POST http://localhost:8080/agent/runs \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"human","content":"What is LangGraph?"}]}'
```

The response returns the streamed events so you can inspect the trace contents or forward them to clients.
