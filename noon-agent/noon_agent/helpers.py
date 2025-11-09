"""Helper utilities for Noon agent."""

import logging

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

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
    logger.info(f"HELPERS: Loaded {len(friends)} friends: {list(friends.keys())}")

    # Get the self user email
    self_email = list(self.values())[0] if self else None
    if self_email:
        friends_context += f"\n\nIMPORTANT: Always include {self_email} in the people list for every event (this is the person scheduling the event)."
        logger.info(f"HELPERS: Self user email: {self_email}")

    logger.info(f"HELPERS: Full friends context:\n{friends_context}")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Extract the user's scheduling intent as a JSON object with exactly these keys: "
                    "action, start_time, end_time, location, people, name, auth_provider, auth_token, summary. "
                    "Use ISO 8601 format for datetime values (e.g. 2025-01-31T14:00:00Z). All events will be in 2025. "
                    "Set any missing or unknown values to null. "
                    "Represent people as a list of email or name strings, even if only one person is provided. "
                    "The 'name' field should contain the event title/subject. "
                    "The 'summary' field should contain additional details or description. "
                    "The action must be one of: create, delete, update, read."
                    f"{friends_context}"
                ),
            ),
            MessagesPlaceholder("messages"),
        ]
    )

    llm = ChatOpenAI(model=model, temperature=temperature)
    structured_llm = llm.with_structured_output(ParsedIntent)

    return prompt | structured_llm
