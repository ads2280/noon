# Database Setup Guide

This guide explains how to set up the Supabase database for the Noon Calendar Agent.

## Overview

The database layer provides:
- **User Management**: Store user profiles with Google OAuth tokens
- **Calendar Management**: Multiple calendars per user
- **Friend Management**: Fuzzy-matched contacts with calendar access
- **Event Caching**: Optional caching of Google Calendar events
- **User Preferences**: Meeting defaults, work hours, etc.

## Architecture

```
User (1)
  ├── Calendars (N) - User's Google Calendars
  ├── Friends (N) - Contacts with calendar access
  ├── UserPreferences (1) - Meeting preferences
  └── OAuth Tokens - Access & refresh tokens
```

## Database Tables

### 1. `users`
Stores user profiles and OAuth tokens.

**Key Fields:**
- `id` (UUID) - Primary key
- `email` (TEXT, UNIQUE) - User's email
- `full_name` (TEXT) - Display name
- `timezone` (TEXT) - User's timezone (e.g., "America/Los_Angeles")
- `google_access_token` (TEXT) - OAuth access token
- `google_refresh_token` (TEXT) - OAuth refresh token
- `google_token_expiry` (TIMESTAMP) - Token expiration
- `primary_calendar_id` (TEXT) - User's primary calendar

### 2. `calendars`
Stores user's Google Calendars (synced from Google).

**Key Fields:**
- `id` (UUID) - Primary key
- `user_id` (UUID) - Foreign key to users
- `google_calendar_id` (TEXT) - Google Calendar ID
- `name` (TEXT) - Calendar name
- `is_primary` (BOOLEAN) - Whether this is the primary calendar

**Unique Constraint:** `(user_id, google_calendar_id)`

### 3. `friends`
Stores user's contacts with calendar access.

**Key Fields:**
- `id` (UUID) - Primary key
- `user_id` (UUID) - Foreign key to users
- `name` (TEXT) - Friend's display name
- `email` (TEXT) - Friend's email
- `google_calendar_id` (TEXT) - Friend's calendar ID (if shared)
- `notes` (TEXT) - Optional notes

**Unique Constraint:** `(user_id, email)`

### 4. `calendar_events` (Optional Cache)
Caches events from Google Calendar for faster queries.

**Key Fields:**
- `id` (UUID) - Primary key
- `google_event_id` (TEXT) - Google Calendar event ID
- `calendar_id` (UUID) - Foreign key to calendars
- `summary` (TEXT) - Event title
- `start_time` (TIMESTAMP) - Event start
- `end_time` (TIMESTAMP) - Event end
- `attendees` (TEXT[]) - List of attendee emails

**Note:** This is a cache. Google Calendar is the source of truth.

### 5. `user_preferences`
Stores user's meeting preferences.

**Key Fields:**
- `id` (UUID) - Primary key
- `user_id` (UUID) - Foreign key to users (UNIQUE)
- `default_meeting_duration` (INTEGER) - Default duration in minutes
- `work_start_hour` (INTEGER) - Work day start (0-23)
- `work_end_hour` (INTEGER) - Work day end (0-23)
- `work_days` (INTEGER[]) - Work days (1=Mon, 7=Sun)
- `buffer_between_meetings` (INTEGER) - Buffer in minutes
- `allow_overlapping_events` (BOOLEAN)

## Setup Steps

### 1. Create Supabase Project

1. Go to [Supabase Dashboard](https://app.supabase.com/)
2. Click "New Project"
3. Name your project (e.g., "noon-calendar")
4. Set a strong database password
5. Select a region close to your users
6. Click "Create new project"

### 2. Run SQL Migration

1. Go to the SQL Editor in your Supabase dashboard
2. Copy the contents of `migrations/001_initial_schema.sql`
3. Paste into the SQL Editor
4. Click "Run" to execute the migration
5. Verify all tables were created successfully

### 3. Get Supabase Credentials

1. Go to Project Settings → API
2. Copy your Project URL (e.g., `https://abc123.supabase.co`)
3. Copy your `anon` public key (for client-side) or `service_role` key (for server-side)

**Important:** Use `service_role` key for backend API, never expose it to clients!

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Supabase
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-service-role-key

# OpenAI (for LLM routing)
OPENAI_API_KEY=sk-...
```

### 5. Install Dependencies

```bash
cd noon-agent
uv sync
```

This installs the `supabase` Python client.

## Usage Examples

### Load User Context from Database

```python
from noon_agent.db_context import load_user_context_from_db

# Load complete user context for the agent
user_context = load_user_context_from_db(user_id="123e4567-e89b-12d3-a456-426614174000")

# user_context now contains:
# - user_id, timezone
# - primary_calendar_id, all_calendar_ids
# - friends list
# - upcoming events
# - access_token
```

### Create or Get User

```python
from noon_agent.db_context import get_or_create_user_by_email

user = get_or_create_user_by_email(
    email="alice@example.com",
    full_name="Alice Johnson"
)
print(f"User ID: {user.id}")
```

### Update OAuth Tokens

```python
from noon_agent.db_context import update_user_tokens
from datetime import datetime, timedelta

update_user_tokens(
    user_id="123e4567-e89b-12d3-a456-426614174000",
    access_token="ya29.new-token...",
    refresh_token="1//new-refresh...",
    expiry=datetime.utcnow() + timedelta(hours=1)
)
```

### Sync Calendars from Google

```python
from noon_agent.db_context import sync_user_calendars_from_google

calendars = sync_user_calendars_from_google(
    user_id="123e4567-e89b-12d3-a456-426614174000",
    access_token="ya29.access-token..."
)

print(f"Synced {len(calendars)} calendars")
```

### Direct Database Queries

```python
from noon_agent.database import get_supabase_client

db = get_supabase_client()

# Get all calendars for a user
result = db.table("calendars").select("*").eq("user_id", user_id).execute()
calendars = result.data

# Add a new friend
friend_data = {
    "user_id": user_id,
    "name": "Bob Smith",
    "email": "bob@example.com",
    "google_calendar_id": "bob@example.com"
}
result = db.table("friends").insert(friend_data).execute()
```

## Security: Row Level Security (RLS)

All tables have Row Level Security enabled. Users can only:
- View their own data
- Modify their own data
- Access events from their own calendars

RLS policies use Supabase Auth (`auth.uid()`) to enforce access control.

**Example:**
```sql
-- Users can only see their own calendars
CREATE POLICY "Users can view own calendars" ON calendars
    FOR SELECT USING (auth.uid()::TEXT = user_id::TEXT);
```

## Database Indexes

Optimized indexes for common queries:

### Fast Lookups
- `idx_users_email` - Find users by email
- `idx_calendars_user_id` - Find user's calendars
- `idx_friends_user_id` - Find user's friends

### Time Range Queries
- `idx_events_time_range` - Find events in date range

### Full-Text Search
- `idx_events_summary` - Search events by title

## Schema Diagram

```
┌──────────────┐
│    users     │
├──────────────┤
│ id (PK)      │
│ email        │◄───────┐
│ timezone     │        │
│ *_token      │        │
└──────────────┘        │
       │                │
       │ 1:N            │
       ▼                │
┌──────────────┐        │
│  calendars   │        │
├──────────────┤        │
│ id (PK)      │        │
│ user_id (FK) │────────┘
│ google_cal_id│
└──────────────┘
       │
       │ 1:N
       ▼
┌──────────────┐
│calendar_events
├──────────────┤
│ id (PK)      │
│ calendar_id  │
│ summary      │
│ start_time   │
└──────────────┘

┌──────────────┐
│   friends    │
├──────────────┤
│ id (PK)      │
│ user_id (FK) │────────┐
│ name         │        │
│ email        │        │
└──────────────┘        │
                        │
┌──────────────┐        │
│user_prefs    │        │
├──────────────┤        │
│ id (PK)      │        │
│ user_id (FK) │────────┘
│ work_hours   │
└──────────────┘
```

## Troubleshooting

### "Failed to connect to Supabase"
- Check `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Verify your Supabase project is active
- Check network connectivity

### "Permission denied"
- Ensure RLS policies are set up correctly
- Verify you're using the correct `service_role` key for backend operations
- Check that `auth.uid()` matches the user_id

### "User not found"
- Ensure user was created in the database
- Check the user_id format (should be UUID)
- Verify the email exists in the `users` table

## Best Practices

1. **Use service_role key for backend**: Never expose it to clients
2. **Refresh tokens regularly**: Update when Google tokens expire
3. **Sync calendars periodically**: Keep calendar list up to date
4. **Cache events selectively**: Only cache if needed for performance
5. **Set proper indexes**: Add indexes for your query patterns

## Migration Guide

To add new columns or tables:

1. Create a new migration file: `migrations/002_your_change.sql`
2. Write the SQL (CREATE TABLE, ALTER TABLE, etc.)
3. Test locally first
4. Run in Supabase SQL Editor
5. Update `models.py` with new Pydantic models

Example:
```sql
-- migrations/002_add_user_photo.sql
ALTER TABLE users ADD COLUMN photo_url TEXT;
```

Then update `models.py`:
```python
class User(UserBase):
    # ... existing fields ...
    photo_url: Optional[str] = None
```
