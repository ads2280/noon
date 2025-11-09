"""Helper utilities for Noon agent."""

import logging

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from datetime import datetime

from .schemas import ParsedIntent
from .constants import friends, self

logger = logging.getLogger(__name__)


def build_intent_parser(model: str = "gpt-4o-mini", temperature: float = 0.2):
    """Return a runnable that turns chat history into a ParsedIntent."""
    logger.info(f"HELPERS: Building intent parser with model={model}, temperature={temperature}")

    # Build friends context for the prompt
    friends_context = "\n\nKnown friends and their emails:\n"
    for name, email in friends.items():
        friends_context += f"- {name}: {email}\n"
    friends_context += (
        "\nWhen a friend's name is mentioned, use their email address in the people list."
    )
    # The new, enhanced system prompt string
    system_prompt = f"""
    You are an expert scheduling assistant. Your task is to extract the user's scheduling intent into a single, precise JSON object.

    **Context:**
    * **Current Time:** {datetime.now().replace(microsecond=0).isoformat() + "Z"}
    * **User's Time Zone:** {{user_timezone}}
    * **Known Contacts:** {friends_context}

    **JSON Output Rules:**
    1.  **Format:** Output a single JSON object with *exactly* these keys: `action`, `start_time`, `end_time`, `location`, `people`, `name`, `auth_provider`, `auth_token`, `summary`.
    2.  **Missing Values:** Set any missing or unknown values to `null`.
    3.  **Action Key:** `action` is mandatory. It *must* be one of: `create`, `delete`, `update`, `read`.
    4.  **Fallback:** If the user's message is ambiguous or clearly not a scheduling request (e.g., 'Hello', 'What's the weather?'), set `action` to `null` along with all other fields.

    **Field-Specific Rules:**
    1.  **Datetimes (`start_time`, `end_time`):**
        * **Format:** Must be in ISO 8601 UTC format (e.g., `2025-01-31T14:00:00Z`).
        * **Inference:** Use the `{current_datetime}` and `{user_timezone}` to resolve all relative times (e.g., 'tomorrow at 10 AM', 'in 2 hours', 'next Friday').
        * **Year:** Infer the correct year based on the `{current_datetime}`. Assume dates mentioned without a year (e.g., 'May 10th') refer to the *next* upcoming instance of that date.

    2.  **People:**
        * **Format:** Must be a list of strings (e.g., `['bob@example.com']`, `['Alice', 'Bob']`).
        * **Context:** Use the `{friends_context}` to resolve ambiguous names (e.g., 'Bob') to their full names or emails if possible.

    3.  **Summary vs. Name:**
        * **Summary:** Use this for the event's main title or description (e.g., 'Dentist Appointment', 'Lunch with team').
        * **Name:** Use this *only* when the user is trying to identify an *existing* event, typically for `update` or `delete` actions (e.g., 'delete my meeting named **Budget Review**'). For `create` actions, this should usually be `null`.
    """

    # Create the final prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("messages"),
        ]
    )

    llm = ChatOpenAI(model=model, temperature=temperature)
    structured_llm = llm.with_structured_output(ParsedIntent)

    return prompt | structured_llm
