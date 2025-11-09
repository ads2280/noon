# Async Agent Architecture

## Overview

This document outlines the architecture for asynchronous agent processing, request logging, and pattern analysis.

## Database Schema

### 1. Request Logs (`request_logs`)

Stores all incoming user requests for pattern analysis and ruleset building.

**Key Fields:**
- `user_id` - User who made the request
- `endpoint` - API endpoint (e.g., `/agent/chat`)
- `request_body` - Full request payload (JSONB)
- `response_status` - HTTP status code
- `response_time_ms` - Response time
- `agent_action` - Agent action taken (create, read, update, delete, search, schedule)
- `agent_tool` - Tool name
- `agent_success` - Whether operation succeeded
- `intent_category` - Extracted intent (e.g., 'schedule_meeting', 'view_calendar')
- `entities` - Extracted entities (people, times, locations) - JSONB
- `user_pattern` - Identified user pattern/rule

**Use Cases:**
- Build rulesets from common patterns
- Analyze user behavior
- Improve agent responses
- Detect anomalies

### 2. Async Agent Jobs (`async_agent_jobs`)

Manages background jobs for calendar processing.

**Key Fields:**
- `user_id` - User for the job
- `job_type` - Type: 'calendar_sync', 'event_reminder', 'pattern_analysis', 'bulk_operation'
- `job_status` - 'pending', 'running', 'completed', 'failed', 'cancelled'
- `priority` - 1 (highest) to 10 (lowest)
- `payload` - Job-specific parameters (JSONB)
- `agent_state` - Full LangGraph agent state (JSONB)
- `scheduled_at` - When to run
- `retry_count` - Retry attempts

**Job Types:**

1. **calendar_sync** - Sync calendar events from Google Calendar
   - Payload: `{"calendar_ids": [...], "time_range": {...}}`
   
2. **event_reminder** - Send reminders for upcoming events
   - Payload: `{"event_id": "...", "reminder_time": "..."}`
   
3. **pattern_analysis** - Analyze user patterns from request logs
   - Payload: `{"time_range": {...}, "pattern_type": "..."}`
   
4. **bulk_operation** - Perform bulk operations on events
   - Payload: `{"operation": "update", "event_ids": [...], "changes": {...}}`

## Request Logging

### Middleware

`RequestLoggingMiddleware` automatically logs all requests:
- Extracts user ID from JWT token
- Logs request/response details
- Extracts agent-specific fields
- Stores in `request_logs` table

### Usage

The middleware is automatically added to the FastAPI app in `app.py`:

```python
app.add_middleware(
    RequestLoggingMiddleware,
    exclude_paths=["/healthz", "/docs", "/openapi.json", "/redoc"],
)
```

### Logging in Endpoints

For agent endpoints, you can enhance logs with agent-specific data:

```python
from services.request_logging import log_agent_request

@router.post("/agent/chat")
async def chat_with_agent(...):
    # ... agent processing ...
    
    # Log with agent details
    log_agent_request(
        user_id=current_user.id,
        endpoint="/agent/chat",
        agent_action=full_result.get("action"),
        agent_tool=tool_name,
        agent_success=success,
        agent_summary=summary,
        intent_category=extract_intent(payload.text),
        entities=extract_entities(payload.text),
    )
```

## Async Agent Service

### Creating Jobs

```python
from services.async_agent import async_agent_service, JobType

# Create a calendar sync job
job_id = async_agent_service.create_job(
    user_id=user.id,
    job_type=JobType.CALENDAR_SYNC,
    payload={
        "calendar_ids": ["primary"],
        "time_range": {
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-31T23:59:59Z",
        }
    },
    priority=3,  # High priority
)

# Schedule a reminder job
job_id = async_agent_service.create_job(
    user_id=user.id,
    job_type=JobType.EVENT_REMINDER,
    payload={
        "event_id": "abc123",
        "calendar_id": "primary",
        "reminder_time": "2024-01-15T14:00:00Z",
    },
    scheduled_at=datetime(2024, 1, 15, 13, 0),  # 1 hour before event
    priority=1,  # Highest priority
)
```

### Processing Jobs

Create a background worker to process jobs:

```python
# workers/agent_worker.py
import asyncio
from services.async_agent import async_agent_service, JobType
from noon_agent.main import graph

async def process_jobs():
    while True:
        jobs = async_agent_service.get_pending_jobs(limit=10)
        
        for job in jobs:
            try:
                # Mark as running
                async_agent_service.update_job_status(job["id"], "running")
                
                # Execute agent with stored state
                result = graph.invoke(job["agent_state"])
                
                # Mark as completed
                async_agent_service.update_job_status(
                    job["id"],
                    "completed",
                    result={"status": "success", "data": result}
                )
            except Exception as e:
                # Retry or mark as failed
                if job["retry_count"] < job["max_retries"]:
                    async_agent_service.retry_job(job["id"])
                else:
                    async_agent_service.update_job_status(
                        job["id"],
                        "failed",
                        error_message=str(e)
                    )
        
        await asyncio.sleep(5)  # Poll every 5 seconds
```

## Pattern Analysis

### Extracting Patterns

Query `request_logs` to identify patterns:

```sql
-- Find most common agent actions per user
SELECT 
    user_id,
    agent_action,
    COUNT(*) as count,
    AVG(response_time_ms) as avg_response_time,
    AVG(CASE WHEN agent_success THEN 1 ELSE 0 END) as success_rate
FROM request_logs
WHERE agent_action IS NOT NULL
GROUP BY user_id, agent_action
ORDER BY count DESC;

-- Find common intent patterns
SELECT 
    intent_category,
    COUNT(*) as frequency,
    jsonb_agg(DISTINCT entities) as common_entities
FROM request_logs
WHERE intent_category IS NOT NULL
GROUP BY intent_category
ORDER BY frequency DESC;

-- Identify user-specific patterns
SELECT 
    user_id,
    agent_action,
    jsonb_object_agg(
        key, value
    ) FILTER (WHERE key IN ('people', 'location', 'time'))
    as common_patterns
FROM request_logs,
     jsonb_each(entities) as pattern
WHERE user_id = '...'
GROUP BY user_id, agent_action;
```

### Building Rulesets

Use pattern analysis to build user-specific rules:

```python
def build_user_ruleset(user_id: str) -> Dict[str, Any]:
    """Build ruleset from user's request patterns."""
    # Query common patterns
    # Extract rules (e.g., "always schedule coffee meetings at 3pm")
    # Return structured ruleset
    pass
```

## UserContext Storage

Currently, `UserContext` is constructed on-the-fly from:
- `users` table
- `calendars` table  
- `friends` table
- Google Calendar API (upcoming events)

### Optional: UserContext Cache

For performance, you could add a cache table:

```sql
create table if not exists public.user_context_cache (
    user_id uuid primary key references public.users (id) on delete cascade,
    context_data jsonb not null,
    expires_at timestamptz not null,
    updated_at timestamptz not null default timezone('utc'::text, now())
);
```

This would cache the constructed UserContext with a TTL.

## Implementation Checklist

- [x] Create `request_logs` table migration
- [x] Create `async_agent_jobs` table migration
- [x] Create `RequestLoggingMiddleware`
- [x] Create `AsyncAgentService`
- [ ] Create background worker for processing jobs
- [ ] Add pattern extraction to agent endpoints
- [ ] Create pattern analysis queries
- [ ] Build ruleset generation from patterns
- [ ] (Optional) Add UserContext cache table

