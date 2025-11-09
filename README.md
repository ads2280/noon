# Noon
```
   _   _   .-----.   .-----.  _   _
  | \ | |  / 12 ^ \ / 12 ^ \ | \ | |
  |  \| | |  \ |  ||  | /  | |  \| |
  | |\  | |  / o  ||  o \  | | |\  |
  |_| \_|  \__6__/  \__6__/  |_| \_|
  it's time, but it's really simple.
```

> built by chronically reflective students who can't stop thinking about how we trade slices of our lives for calendar blocks.

Noon is a time-first assistant: a SwiftUI app, a FastAPI backend, an LLM calendar agent, a Supabase brain, and a Deepgram-powered transcription sidekick. Every folder here is a piece of the same argument — that better tooling can make our days feel intentional instead of reactionary.

## Why This Exists
- Calendars hide the why behind events; Noon tries to keep context attached to scheduling.
- Agents are powerful, but only if they can hit production-grade APIs (Google Calendar, Supabase auth, Deepgram) without drama.

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

## What Noon Actually Does
- **Transcribes intent**: the iOS mic hands raw audio to `noon-v2nl`, which boosts key vocabulary and returns articulate transcripts via Deepgram.
- **Understands the request**: that transcript plus device context becomes a LangGraph run where the Noon agent chooses a calendar tool (list, create, update, delete).
- **Executes safely**: agent outputs are validated against the schemas in `noon-agent/main.py` before the backend forwards anything to Google Calendar.
- **Keeps people signed in**: `noon-backend` connects Supabase phone OTP login with Google OAuth so linking accounts feels like texting a friend, not filling out a form.
- **Stays in sync**: Supabase migrations ship the same schema everywhere, so analytics, notifications, and agents all speak the same database language.

## Why This Is Cool
- **Voice is treated as a first-class UI**: the transcription service isn’t an afterthought—it’s tuned to respect custom vocab and different accents so spoken intent survives round trips.
- **Agents with guardrails**: every operation is a typed contract, which means the LLM can be creative in planning but precise in execution.
- **Human-friendly design system**: the SwiftUI palette (`ColorPalette.Semantic`, `.Text`, `.Surface`, `.Gradients`) turns “ship fast” into “ship fast without breaking visual consistency.”
- **Modular by design**: each directory can evolve independently; swap a model, redesign the app shell, or update auth flows without breaking the rest.
- **Doc-traceable decisions**: the repo doubles as a notebook—older agent prototypes, API response types, and curl walkthroughs are preserved so future contributors inherit context, not mysteries.

## Why It Matters
- Time is the scarcest resource students (and honestly everyone) trade; Noon tries to keep the intent behind every event intact.
- Scheduling tools rarely respect nuance (half-hour offsets, recurring-but-conditional meetings, emotional context). Noon’s agent framework is built to capture that nuance.
- Bridging consumer UX (SwiftUI) with production infra (Supabase, FastAPI, LangGraph, Deepgram) is the only way agents feel trustworthy. This repo proves that bridge can be clear, tested, and personable.
- Building in the open—migrations, schemas, agent contracts—means others can remix these ideas into their own time-respecting products.

## Evidence of Care
- `noon-backend/AGENT_API_ENDPOINTS.md` and `AGENT_API_RESPONSE_TYPES.md` explain exactly how the backend and agent talk so you can reason about every tool call.
- `noon-agent-old/CALENDAR_AGENT_README.md` chronicles prior behaviors, giving you regression history when something feels off.
- `noon-backend/TESTING_CURL_REQUESTS.md` reads like a lab notebook for the API; copy/paste tests are there when you need them.
- The SwiftUI color palette and Deepgram proxy aren’t just utilities—they’re case studies on how to treat supporting services with the same intentionality as the headline feature.

If you ended up here because you care about time, welcome. Commit often, test the odd cases (recurring events, time zones that jump half-hours), and keep asking whether the product is reducing cognitive load. That question is the real spec.
