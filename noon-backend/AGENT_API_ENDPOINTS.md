# Agent API Endpoints

This document outlines all available endpoints for the frontend to interact with the calendar agent.

## Base URL

All endpoints are relative to your backend base URL (e.g., `https://api.noon.com` or `http://localhost:8000`).

## Authentication

All agent endpoints require authentication via Bearer token in the `Authorization` header:

```
Authorization: Bearer <your_jwt_token>
```

---

## Agent Endpoints

### POST `/agent/chat`

Send natural language text to the calendar agent and get structured responses.

**Request:**
```http
POST /agent/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "text": "Schedule a meeting tomorrow at 2pm"
}
```

**Request Body Schema:**
```typescript
{
  text: string;  // Natural language input
}
```

**Response:**
```json
{
  "tool": "create",
  "summary": "Created event: Meeting at 2024-01-15T14:00:00",
  "result": {
    "status": "success",
    "event_id": "abc123xyz",
    "summary": "Meeting",
    "start": "2024-01-15T14:00:00",
    "end": "2024-01-15T15:00:00",
    "link": "https://www.google.com/calendar/event?eid=..."
  },
  "success": true
}
```

**Response Schema:**
```typescript
{
  tool: "create" | "read" | "search" | "update" | "delete" | "schedule";
  summary: string;
  result: object | null;
  success: boolean;
}
```

**Example Requests:**

1. **Create Event:**
   ```json
   {
     "text": "Schedule a team meeting tomorrow at 2pm for 1 hour"
   }
   ```

2. **Read Events:**
   ```json
   {
     "text": "Show me my events this week"
   }
   ```

3. **Search Events:**
   ```json
   {
     "text": "Find all meetings with Alice"
   }
   ```

4. **Update Event:**
   ```json
   {
     "text": "Move the team meeting to 3pm"
   }
   ```

5. **Delete Event:**
   ```json
   {
     "text": "Cancel the team meeting"
   }
   ```

6. **Get Schedule:**
   ```json
   {
     "text": "What's my schedule from Monday to Friday?"
   }
   ```

**Status Codes:**
- `200 OK` - Request successful
- `400 Bad Request` - Invalid request or missing Google account
- `401 Unauthorized` - Invalid or expired token
- `500 Internal Server Error` - Agent invocation failed

**Error Response Example:**
```json
{
  "detail": "User has no Google Calendar access token. Please link your Google account first."
}
```

---

### POST `/agent/event`

Get full event details by event ID and calendar ID, along with the day's schedule.

**Request:**
```http
POST /agent/event
Authorization: Bearer <token>
Content-Type: application/json

{
  "event_id": "abc123xyz",
  "calendar_id": "primary"
}
```

**Request Body Schema:**
```typescript
{
  event_id: string;        // Required: Event ID from Google Calendar
  calendar_id?: string;    // Optional: Calendar ID (defaults to "primary")
}
```

**Response:**
```json
{
  "event": {
    "status": "success",
    "event_id": "abc123xyz",
    "summary": "Team Meeting",
    "description": "Weekly team sync",
    "location": "Conference Room A",
    "start": "2024-01-15T14:00:00",
    "end": "2024-01-15T15:00:00",
    "timezone": "America/Los_Angeles",
    "attendees": [
      {
        "email": "alice@example.com",
        "displayName": "Alice",
        "responseStatus": "accepted"
      }
    ],
    "organizer": {
      "email": "user@example.com",
      "displayName": "User Name"
    },
    "event_link": "https://www.google.com/calendar/event?eid=...",
    "created": "2024-01-10T10:00:00Z",
    "updated": "2024-01-12T11:00:00Z",
    "calendar_id": "primary",
    "recurrence": [],
    "reminders": {}
  },
  "day_schedule": {
    "status": "success",
    "count": 5,
    "events": [
      {
        "event_id": "event1",
        "summary": "Morning Standup",
        "start": "2024-01-15T09:00:00",
        "end": "2024-01-15T09:30:00",
        "description": ""
      },
      {
        "event_id": "abc123xyz",
        "summary": "Team Meeting",
        "start": "2024-01-15T14:00:00",
        "end": "2024-01-15T15:00:00",
        "description": "Weekly team sync"
      },
      // ... more events for that day
    ]
  },
  "success": true
}
```

**Response Schema:**
```typescript
{
  event: {
    status: "success";
    event_id: string;
    summary: string;
    description: string;
    location: string;
    start: string;  // ISO 8601 datetime
    end: string;    // ISO 8601 datetime
    timezone: string;
    attendees: Array<{
      email: string;
      displayName: string;
      responseStatus: string;
    }>;
    organizer: {
      email: string;
      displayName: string;
    } | null;
    event_link: string | null;
    created: string;
    updated: string;
    calendar_id: string;
    recurrence: string[];
    reminders: object;
  };
  day_schedule: {
    status: "success";
    count: number;
    events: Array<{
      event_id: string;
      summary: string;
      start: string;
      end: string;
      description: string;
    }>;
  };
  success: boolean;
}
```

**Status Codes:**
- `200 OK` - Request successful
- `400 Bad Request` - Invalid request or missing Google account
- `401 Unauthorized` - Invalid or expired token
- `404 Not Found` - Event not found
- `500 Internal Server Error` - Server error

**Example Request:**
```bash
curl -X POST "http://localhost:8000/agent/event" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "abc123xyz",
    "calendar_id": "primary"
  }'
```

---

## Health Check

### GET `/healthz`

Check if the API is running.

**Request:**
```http
GET /healthz
```

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200 OK` - Service is healthy

---

## Related Endpoints

### Authentication Endpoints

These are required before using the agent:

- `POST /auth/otp` - Request OTP for phone authentication
- `POST /auth/verify` - Verify OTP and get access token

### Google Account Endpoints

These are required to link Google Calendar:

- `GET /google-accounts/` - List linked Google accounts
- `POST /google-accounts/oauth/start` - Start Google OAuth flow
- `GET /google-accounts/oauth/callback` - OAuth callback (handled by backend)
- `POST /google-accounts/` - Create/link Google account
- `DELETE /google-accounts/{account_id}` - Unlink Google account

---

## Complete Frontend Flow

1. **Authenticate User:**
   ```
   POST /auth/otp
   POST /auth/verify
   → Get JWT token
   ```

2. **Link Google Account (if not already linked):**
   ```
   POST /google-accounts/oauth/start
   → Redirect user to Google OAuth
   → User authorizes
   → Backend handles callback
   ```

3. **Use Agent (Natural Language):**
   ```
   POST /agent/chat
   Authorization: Bearer <token>
   {
     "text": "Show me my schedule this week"
   }
   → Get structured response with events
   ```

4. **Get Specific Event Details:**
   ```
   POST /agent/event
   Authorization: Bearer <token>
   {
     "event_id": "abc123xyz",
     "calendar_id": "primary"
   }
   → Get full event details + day's schedule
   ```

---

## TypeScript Example

```typescript
interface AgentChatRequest {
  text: string;
}

interface AgentChatResponse {
  tool: "create" | "read" | "search" | "update" | "delete" | "schedule";
  summary: string;
  result: Record<string, any> | null;
  success: boolean;
}

async function chatWithAgent(
  text: string,
  token: string
): Promise<AgentChatResponse> {
  const response = await fetch(`${API_BASE_URL}/agent/chat`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Agent request failed");
  }

  return response.json();
}

// Usage
const result = await chatWithAgent(
  "Schedule a meeting tomorrow at 2pm",
  userToken
);

console.log(result.tool);      // "create"
console.log(result.summary);   // "Created event: Meeting at..."
console.log(result.result);    // { event_id: "...", ... }
console.log(result.success);   // true
```

---

## Notes

- The agent endpoint accepts natural language input and automatically determines the action
- All operations require a linked Google Calendar account
- The `result` field contains structured data specific to each operation type
- See `AGENT_API_RESPONSE_TYPES.md` for detailed response structures

