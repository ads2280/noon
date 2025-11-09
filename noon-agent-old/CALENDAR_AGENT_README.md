# Noon Calendar Agent

A LangGraph-based intelligent calendar agent with Google Calendar integration, multi-calendar overlay support, and natural language processing.

## Features

### Core Capabilities
- **Create Events**: Schedule meetings with natural language
- **Update Events**: Modify existing calendar events
- **Delete Events**: Remove events from calendar
- **Search Events**: Find events using fuzzy text matching
- **View Schedule**: Get unified view across all calendars (overlay)
- **Check Availability**: Find free time slots across all your calendars
- **Find Overlap**: Discover mutual availability with friends/colleagues

### Advanced Features
- **Multi-Calendar Overlay**: Combines events from all your calendars to show true availability
- **Friend Resolution**: Uses fuzzy name matching to resolve attendees
- **Relative Time Parsing**: Understands "tomorrow", "next week", etc.
- **LLM-Based Intent Classification**: Natural language understanding via GPT-4
- **Timezone Support**: Handles user timezones correctly

## Single Endpoint Contract (Breaking Change)

The helper now exposes one JSON endpoint. Send a payload with a `query` string (plus optional
`auth_token`, `calendar_id`, and `context`) and you'll receive a discriminated union response.
The legacy `{messages: [...]}` and `{response, success, action}` shapes have been removed.

| Tool            | Purpose                  | Shape (examples)                                                                 |
|-----------------|--------------------------|----------------------------------------------------------------------------------|
| `show`          | Display a specific event | `{ "tool": "show", "id": "evt_123", "calendar": "primary" }`                     |
| `show-schedule` | Display a date range     | `{ "tool": "show-schedule", "start_day": "2024-09-01", "end_day": "2024-09-07" }`|
| `create`        | Confirm event creation   | `{ "tool": "create", "summary": "...", "start_time": "...", ... }`               |
| `update`        | Describe applied edits   | `{ "tool": "update", "id": "evt_123", "changes": { "summary": "New title" } }`   |
| `delete`        | Confirm deletion         | `{ "tool": "delete", "id": "evt_123", "calendar": "primary" }`                   |

Each response may include additional contextual fields (e.g., attendees, metadata, match lists) but
the `tool` literal and core identifiers above are always present.

## Architecture

### Two-Layer Design

#### Layer 1: Low-Level API (`tools/gcal_api.py`)
Direct Google Calendar API operations for single calendars:
- `create_event_api()`
- `update_event_api()`
- `delete_event_api()`
- `list_events_api()`
- `get_freebusy_api()`

#### Layer 2: High-Level Tools (`tools/gcal_tools.py`)
LLM-callable tools that can overlay multiple calendars:
- `create_event()` - Create events
- `search_events()` - Search across ALL calendars
- `get_schedule()` - Unified schedule view
- `check_availability()` - Free time across ALL calendars
- `find_overlap()` - Mutual availability with others

### LangGraph Structure

```
START
  ↓
route_intent (LLM classifies intent and extracts parameters)
  ↓
[Conditional Routing]
  ├── create_event
  ├── update_event
  ├── delete_event
  ├── search_events
  ├── get_schedule
  ├── check_availability
  ├── find_overlap
  └── acknowledge
  ↓
END
```

### State Management

The `CalendarAgentState` flows through the graph and contains:
- `input`: User's natural language input
- `current_time`: Current timestamp for relative time parsing
- `user_context`: User info including access token, timezone, calendars, friends
- `intent`: Classified intent (set by routing node)
- `parameters`: Extracted parameters (set by routing node)
- `result`: Tool execution result
- `response`: Final response to user
- Error and clarification fields

## Setup

### 1. Install Dependencies

```bash
cd noon-agent
pip install -e .
```

### 2. Google Calendar API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials:
   - Application type: Desktop app
   - Download credentials as `credentials.json`
5. Place `credentials.json` in the project root

### 3. Environment Variables

Create a `.env` file:

```env
OPENAI_API_KEY=sk-...
```

### 4. First Run (OAuth)

Run the OAuth flow to get your token:

```python
from noon_agent import get_calendar_service_from_file

# This will open a browser for OAuth
service = get_calendar_service_from_file(
    credentials_path="credentials.json",
    token_path="token.json"
)
```

A `token.json` file will be created for future use.

## Usage

### Basic Example

```python
from noon_agent import invoke_agent

payload = {
    "query": "Schedule a meeting with Alice tomorrow at 2pm",
    "auth_token": "ya29....",
    "calendar_id": "primary",
    "context": {"timezone": "America/Los_Angeles"},
}

result = invoke_agent(payload)
if result["tool"] == "create":
    print(f"Created event {result['id']} on {result['calendar']}")
```

### Production API Integration

In a production API (FastAPI, Flask, etc.), you'd use this pattern:

```python
from fastapi import FastAPI, Request
from noon_agent import invoke_agent

app = FastAPI()

@app.post("/calendar/agent")
async def run_agent(request: Request):
    body = await request.json()
    # Body must at least contain {"query": "..."}
    result = invoke_agent(body)
    return result
```

## Example Queries

### Create Events
```
"Schedule a meeting with Alice tomorrow at 2pm"
"Create a 30-minute standup every weekday at 9am"
"Book lunch with the team next Friday at noon"
```

### Check Availability
```
"When am I free tomorrow?"
"Find a 2-hour slot next week"
"Show me my availability on Friday afternoon"
```

### Find Mutual Availability
```
"When can Alice and I meet next week?"
"Find a time when Bob, Carol, and I are all free on Wednesday"
```

### Search Events
```
"Find all my meetings about Q4 planning"
"Show me events with Alice this week"
```

### View Schedule
```
"What's on my calendar tomorrow?"
"Show my schedule for next week"
"What do I have today?"
```

## Multi-Calendar Overlay

The agent automatically overlays all your calendars to provide accurate availability:

```python
# User has 3 calendars:
# - primary@gmail.com (work)
# - personal@gmail.com (personal)
# - shared-team@example.com (team)

# When checking availability, the agent:
# 1. Queries all 3 calendars
# 2. Merges all busy periods
# 3. Returns only truly free slots

result = invoke_agent({"query": "When am I free tomorrow?", "auth_token": "ya29..."})
# Result considers events from ALL calendars
```

## Friend Resolution

The agent uses fuzzy name matching to resolve attendees:

```python
# User's friends list:
friends = [
    {"name": "Alice Johnson", "email": "alice@example.com", "calendar_id": "alice@example.com"},
    {"name": "Bob Smith", "email": "bob@example.com", "calendar_id": "bob@example.com"}
]

# Query: "Schedule a meeting with Alice tomorrow"
# Agent resolves "Alice" -> "Alice Johnson" -> alice@example.com

# Query: "When can Bob and I meet?"
# Agent resolves "Bob" -> "Bob Smith" -> bob@example.com
# Then checks mutual availability
```

## Extending the Agent

### Add a New Intent

1. **Add to router** (`calendar_router.py`):
```python
# Update ROUTER_SYSTEM_PROMPT with new intent
# Update route_to_action() to handle new intent
```

2. **Create node** (`calendar_nodes.py`):
```python
def my_new_action_node(state: CalendarAgentState) -> Dict[str, Any]:
    # Implement action
    return {...state, "response": "Done!"}
```

3. **Wire to graph** (`calendar_graph.py`):
```python
graph.add_node("my_new_action", my_new_action_node)
graph.add_conditional_edges(..., {"my_new_action": "my_new_action"})
graph.add_edge("my_new_action", END)
```

### Add a New Tool

1. **Low-level API** (`tools/gcal_api.py`):
```python
def my_new_api_call(service, calendar_id, ...):
    # Direct Google Calendar API call
    pass
```

2. **High-level tool** (`tools/gcal_tools.py`):
```python
def my_new_tool(service, calendar_ids: List[str], ...):
    # Call low-level API for each calendar
    # Merge/combine results
    # Return unified result
    pass
```

## Testing

Run the example script:

```bash
python example_usage.py
```

## File Structure

```
noon_agent/
├── __init__.py                 # Package exports
├── calendar_graph.py           # LangGraph definition
├── calendar_router.py          # LLM-based routing
├── calendar_nodes.py           # Action nodes
├── calendar_state.py           # State definitions
├── gcal_auth.py               # Google Calendar auth
├── config.py                   # Settings
├── tools/
│   ├── __init__.py
│   ├── gcal_api.py            # Low-level Google Calendar API
│   ├── gcal_tools.py          # High-level multi-calendar tools
│   ├── friend_tools.py        # Friend resolution
│   └── context_tools.py       # Context management
└── main.py                     # Single-endpoint LangGraph entrypoint
```

## Key Concepts

### Multi-Calendar Overlay

The killer feature! When checking availability or viewing schedule:
1. Agent queries ALL user's calendars
2. Merges events by timestamp
3. Provides unified view
4. Shows true availability (not just primary calendar)

### Friend Resolution

Fuzzy matching allows natural queries:
- "Alice" → "Alice Johnson" (confidence: 0.95)
- "Bob from Engineering" → "Bob Smith" (confidence: 0.85)
- Asks for clarification if multiple matches

### Relative Time Parsing

Understands natural time expressions:
- "tomorrow" → 2024-11-09T00:00:00Z
- "next week" → 2024-11-11T00:00:00Z to 2024-11-18T00:00:00Z
- "Friday afternoon" → 2024-11-10T13:00:00Z to 2024-11-10T17:00:00Z

## Troubleshooting

### "Failed to authenticate"
- Check `credentials.json` is in the project root
- Run OAuth flow again to refresh `token.json`

### "No calendars found"
- Verify Google Calendar API is enabled in Cloud Console
- Check OAuth scopes include calendar access

### "LLM routing failed"
- Verify `OPENAI_API_KEY` is set in `.env`
- Check internet connection

## License

MIT
