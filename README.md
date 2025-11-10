# Noon
```
   _   _   .-----.   .-----.  _   _
  | \ | |  / 12 ^ \ / 12 ^ \ | \ | |
  |  \| | |  \ |  ||  | /  | |  \| |
  | |\  | |  / o  ||  o \  | | |\  |
  |_| \_|  \__6__/  \__6__/  |_| \_|
  it's time, but it's really simple.
```

Calendars take too much time. We waste attention on scheduling instead of doing things. We wanted a simple voice shortcut that hears what you want and gets it on your calendar.

## What it does
iOS app istens to your voice and turns it into text
Understands the intent and produces concrete Google Calendar operations
Executes create, update, delete, list, and get on your calendar
Confirms the result in a clean, fast flow

## Repo Atlas

| Path | Role |
| --- | --- |
| `noon-ios/` | SwiftUI app with a centralized color system and the end-to-end user experience. |
| `noon-backend/` | FastAPI gateway for Supabase phone auth + Google account linking, plus proxying to the LangGraph agent. |
| `noon-agent/` | Current calendar agent (argument planner + tool schemas) that LangGraph or other orchestrators can call. |
| `noon-agent-old/` | Earlier prototype + documentation. Still handy for context and testing ideas. |
| `noon-v2nl/` | “voice-to-natural-language” Deepgram proxy that turns audio blobs into text the agent can understand. |
| `supabase/migrations/` | SQL that defines users, Google accounts, and calendar-centric tables so every environment shares the same schema. |

## System Sketch
1. **User taps the mic in iOS.** Audio streams to `noon-v2nl`, which forwards to Deepgram and returns text.
2. **Text becomes intent.** The iOS app hands the utterance + context to the backend, which forwards it to the LangGraph-hosted Noon agent.
3. **Agent chooses a calendar tool.** Create/update/list/delete payloads are validated (see `noon-agent/main.py`) before touching Google Calendar.
4. **State is synced.** Supabase tracks users, phone-auth sessions, and linked Google accounts; the backend enforces all that.

Everything is modular on purpose — you can iterate on the agent without touching Swift, and vice versa.


