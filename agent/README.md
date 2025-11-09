# Calendar Agent

A LangGraph-based intelligent agent for parsing natural language calendar queries and routing them to appropriate handlers.

## Overview

This agent uses OpenAI's GPT-5-nano with structured outputs to classify user intents and extract metadata for calendar operations. It supports six types of requests:

1. **show-event** - View details of a specific event
2. **show-schedule** - View schedule for a time period
3. **create-event** - Create a new calendar event
4. **update-event** - Modify an existing event
5. **delete-event** - Delete an event
6. **no-action** - Non-calendar queries

## Architecture

```
User Query ’ Intent Classification ’ Handler Routing ’ Metadata Extraction ’ Output
```

### Flow

1. **classify_intent** - LLM classifies the query into one of 6 request types
2. **route_request** - Routes to appropriate handler based on classification
3. **Handler nodes** - Extract structured metadata using LLM structured outputs
4. **Output** - Returns success status, request type, and metadata

## Files

- **main.py** - Core agent implementation with LangGraph
- **prompts.py** - System prompts for LLM instructions
- **test_agent.py** - Comprehensive test suite
- **__init__.py** - Exports `noon_graph`
- **langgraph.json** - LangGraph configuration

## Usage

```python
from agent import noon_graph

# Input state
state = {
    "query": "What am I doing tomorrow?",
    "auth": {...},
    "success": False,
    "request": "no-action",
    "metadata": {}
}

# Invoke the agent
result = noon_graph.invoke(state)

# Output
# {
#     "success": True,
#     "request": "show-schedule",
#     "metadata": {
#         "start-date": "2025-11-10",
#         "end-date": "2025-11-10"
#     }
# }
```

## Handler Details

### show_event
Extracts event identifier for searching calendar by title.

**Output:**
```json
{
  "success": true,
  "metadata": {
    "event-id": "...",
    "calendar-id": "...",
    "search-title": "...",
    "search-description": "..."
  }
}
```

**TODO:** Integrate with backend calendar API to search by title and get actual event-id and calendar-id.

### show_schedule
Parses natural language dates into ISO 8601 format.

**Examples:**
- "tomorrow" ’ Single day range
- "next week" ’ Monday-Sunday range
- "next Monday" ’ Specific day

**Output:**
```json
{
  "success": true,
  "metadata": {
    "start-date": "2025-11-10",
    "end-date": "2025-11-16"
  }
}
```

### create_event
Extracts all event details for creation.

**Output:**
```json
{
  "success": true,
  "metadata": {
    "title": "Meeting with Sarah",
    "start-date": "2025-11-10T14:00:00",
    "end-date": "2025-11-10T15:00:00",
    "location": "123 Main St",
    "attendees": ["sarah@example.com"],
    "description": "Discuss project updates"
  }
}
```

### update_event
Extracts event identifier and new information.

**Output:**
```json
{
  "success": true,
  "metadata": {
    "event-id": "...",
    "calendar-id": "...",
    "search-title": "3pm meeting",
    "start-date": "2025-11-10T16:00:00"
  }
}
```

**TODO:** Integrate with backend calendar API to get current event-id and calendar-id.

### delete_event
Extracts event identifier for deletion.

**Output:**
```json
{
  "success": true,
  "metadata": {
    "event-id": "...",
    "calendar-id": "...",
    "search-title": "meeting with John"
  }
}
```

**TODO:** Integrate with backend calendar API to get event-id and calendar-id.

### do_nothing
Placeholder for non-calendar queries.

**Output:**
```json
{
  "success": true,
  "metadata": {
    "reason": "No calendar action needed"
  }
}
```

## Testing

Run the test suite:

```bash
cd /Users/anika/noon/agent
pytest test_agent.py -v
```

### Test Coverage

- Intent classification for all 6 request types
- Date parsing (tomorrow, next week, specific days, weekends)
- Event creation with various fields
- Event updates (time, location, title)
- Event deletion
- Edge cases (empty queries, ambiguous queries)

## Integration Points

### Backend Calendar API (Future)

Three functions need integration with backend calendar utilities:

1. **show_event** - Search calendar by title to get event-id and calendar-id
2. **update_event** - Search calendar by title to get current event-id and calendar-id
3. **delete_event** - Search calendar by title to get event-id and calendar-id

When backend calendar utils are ready, replace placeholder IDs with actual API calls.

## Configuration

### Model Configuration

The agent uses `openai:gpt-5-nano` with:
- Temperature: 0.7
- Max tokens: 1000
- Configurable fields: temperature, max_tokens, model

### Environment

Ensure `.env` file contains OpenAI API key and other required environment variables.

## Dependencies

- langchain >= 1.0.5
- langgraph >= 1.0.2
- langsmith >= 0.4.42
- pydantic (for structured outputs)
- pytest (for testing)

## Logging

The agent includes comprehensive logging at each step using Python's standard `logging` module.

## Metadata Format

All metadata uses **hyphenated keys** to match backend schema requirements:
- `event-id`, `calendar-id`, `start-date`, `end-date`

Date format: **ISO 8601** (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
