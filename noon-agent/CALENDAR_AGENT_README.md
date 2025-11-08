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
from datetime import datetime
from noon_agent import invoke_calendar_agent
from noon_agent.tools.context_tools import load_user_context
from noon_agent.gcal_auth import get_calendar_service_from_file

# Get calendar service
service = get_calendar_service_from_file()

# Load user context
user_context = load_user_context(
    service=service,
    user_id="user123",
    timezone="America/Los_Angeles"
)

# Note: In production, access_token comes from your API request
user_context["access_token"] = "your-token-here"

# Invoke the agent
result = invoke_calendar_agent(
    user_input="Schedule a meeting with Alice tomorrow at 2pm",
    user_context=user_context,
    current_time=datetime.now()
)

print(result["response"])
```

### Production API Integration

In a production API (FastAPI, Flask, etc.), you'd use this pattern:

```python
from fastapi import FastAPI, Request, Header
from noon_agent import invoke_calendar_agent
from noon_agent import get_calendar_service
from noon_agent.tools.context_tools import load_user_context

app = FastAPI()

@app.post("/calendar/invoke")
async def invoke(request: Request, authorization: str = Header(...)):
    # Extract access token from Authorization header
    access_token = authorization.replace("Bearer ", "")

    # Get user input
    data = await request.json()
    user_input = data["input"]

    # Create service from token
    service = get_calendar_service(access_token)

    # Load user context (from database in production)
    user_context = load_user_context(
        service=service,
        user_id=data["user_id"],
        timezone=data.get("timezone", "UTC")
    )
    user_context["access_token"] = access_token

    # Invoke agent
    result = invoke_calendar_agent(
        user_input=user_input,
        user_context=user_context
    )

    return {"response": result["response"]}
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

result = invoke_calendar_agent(
    user_input="When am I free tomorrow?",
    user_context=user_context
)

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
└── main.py                     # Legacy agent (deprecated)
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
