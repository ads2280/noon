# Noon Agent

This directory hosts a small LangGraph prototype for the Noon project. It exposes a
single assistant-style graph that can be run directly or embedded into other tools.

## Getting started

```bash
cd noon-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # optional, see below for pyproject
```

Alternatively, install dependencies via the `pyproject.toml` with `pip install -e .`
or `uv pip install -e .`.

## Running the graph

```python
from noon_agent import invoke_agent

payload = {
    "query": "Schedule a coffee with Jude tomorrow at 10am.",
    "auth_token": "ya29....",   # OAuth token for Google Calendar
    "calendar_id": "primary",
    "context": {"timezone": "America/Los_Angeles"},
}

response = invoke_agent(payload)
print(response)
# {
#   "tool": "create",
#   "id": "evt_123",
#   "calendar": "primary",
#   "summary": "Coffee with Jude",
#   "start_time": "2024-09-01T10:00:00-07:00",
#   "end_time": "2024-09-01T11:00:00-07:00",
#   ...
# }
```

The agent now has a single JSON interface: it accepts `{"query": "..."}` and returns
one of five tool payloads (`show`, `show-schedule`, `create`, `update`, or `delete`).
See `CALENDAR_AGENT_README.md` for full examples of each response type.
