"""Helper utilities for Noon agent."""

import logging
from datetime import datetime

from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .constants import coffee_shops, friends, restaurants
from .schemas import ParsedIntent

logger = logging.getLogger(__name__)


def build_intent_parser(model: str = "gpt-4o-mini", temperature: float = 0.2):
    """Return a runnable that turns chat history into a ParsedIntent."""
    logger.info(f"HELPERS: Building intent parser with model={model}, temperature={temperature}")

    # Build friends context for the prompt
    friends_context = "Known friends and their emails:\n"
    for name, email in friends.items():
        friends_context += f"  - {name}: {email}\n"

    # Build venue lists for location inference
    coffee_list = "\n".join([f"  - {shop}" for shop in coffee_shops])
    restaurant_list = "\n".join([f"  - {shop}" for shop in restaurants])

    system_prompt = f"""You are an expert scheduling assistant. Extract the user's scheduling intent into a structured JSON object.

**TIMEZONE:** All times are in PST (America/Los_Angeles timezone). Convert all times to PST before outputting.

**CURRENT TIME:** {datetime.now().replace(microsecond=0).isoformat()}

**OUTPUT SCHEMA:**
You must return a JSON object with these exact fields:
- action: REQUIRED - one of: "create", "delete", "update", "read", "search", "schedule"
- start_time: REQUIRED for create action - ISO 8601 datetime in PST (e.g., "2025-01-31T14:00:00-08:00")
- end_time: REQUIRED for create action - ISO 8601 datetime in PST (e.g., "2025-01-31T15:00:00-08:00")
- location: Optional - string for event location/venue
- people: Optional - list of email addresses or names (e.g., ["jude@example.com", "Alice"])
- name: Optional - only for identifying existing events in update/delete actions
- summary: Optional - event title/description (e.g., "Coffee with Jude", "Team lunch")
- event_id: Optional - REQUIRED for update/delete actions - Google Calendar event ID
- calendar_id: Optional - REQUIRED with event_id for update/delete - Calendar ID (defaults to "primary" if not specified)
- auth_provider: Optional - leave null (handled elsewhere)
- auth_token: Optional - leave null (handled elsewhere)

**CRITICAL RULES:**
1. **NEVER leave start_time or end_time as null for create actions** - you MUST infer reasonable values
2. All datetime values MUST be in PST timezone with "-08:00" suffix
3. When a friend's name is mentioned, use their email from the known contacts list

{friends_context}

**SMART TIME INFERENCE:**
When the user doesn't specify end_time, infer it based on the event type:
- Coffee/coffee meetings: 1 hour duration (e.g., "3pm" → start: 3pm, end: 4pm)
- Lunch: 1.5 hour duration, default start at 12:00pm if not specified
- Dinner: 2 hour duration, default start at 7:00pm if not specified
- Generic meetings: 1 hour duration
- If only start time given: add appropriate duration based on event type

**TIME PARSING EXAMPLES:**
- "lunch tomorrow" → start: tomorrow at 12:00pm PST, end: tomorrow at 1:30pm PST
- "coffee at 3pm" → start: today at 3:00pm PST, end: today at 4:00pm PST
- "dinner Friday" → start: next Friday at 7:00pm PST, end: next Friday at 9:00pm PST
- "meeting at 2pm" → start: today at 2:00pm PST, end: today at 3:00pm PST

**SMART LOCATION INFERENCE:**
When event type suggests a venue but no location given, randomly choose from these San Francisco locations:

Coffee shops (for "coffee", "catch up over coffee", etc.):
{coffee_list}

Restaurants (for "lunch", "dinner", "brunch", "eat", etc.):
{restaurant_list}

**EXAMPLES:**

User: "Schedule lunch with jude tomorrow"
Output:
{{{{
  "action": "create",
  "start_time": "2025-01-09T12:00:00-08:00",
  "end_time": "2025-01-09T13:30:00-08:00",
  "location": "Tartine Bakery (Mission)",
  "people": ["jude@partovi.org"],
  "name": null,
  "summary": "Lunch with jude",
  "auth_provider": null,
  "auth_token": null
}}}}

User: "Coffee with anika at 3pm on Friday"
Output:
{{{{
  "action": "create",
  "start_time": "2025-01-10T15:00:00-08:00",
  "end_time": "2025-01-10T16:00:00-08:00",
  "location": "Blue Bottle Coffee (Hayes Valley)",
  "people": ["anika.somaia@columbia.edu"],
  "name": null,
  "summary": "Coffee with anika",
  "auth_provider": null,
  "auth_token": null
}}}}

User: "Delete my team standup"
Output:
{{{{
  "action": "delete",
  "start_time": null,
  "end_time": null,
  "location": null,
  "people": null,
  "name": "team standup",
  "summary": null,
  "auth_provider": null,
  "auth_token": null
}}}}"""

    # Create the final prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("messages"),
        ]
    )

    llm = init_chat_model(model=model, temperature=temperature)
    structured_llm = llm.with_structured_output(ParsedIntent)

    return prompt | structured_llm
