"""Utility helpers for building prompts and LangChain components."""

from typing import Dict

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .config import get_settings
from .schemas import ParsedIntent

SYSTEM_TEMPLATE = (
    "You are Noon, a pragmatic executive assistant. Use the provided context when it is relevant."
)


def build_prompt(extra_instructions: str | None = None) -> ChatPromptTemplate:
    """Return the default chat prompt used by the agent."""

    system_message = SYSTEM_TEMPLATE
    if extra_instructions:
        system_message = f"{system_message}\n\nAdditional instructions: {extra_instructions}"

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )


def build_context_block(context: Dict[str, str] | None) -> str:
    """Render context into a short English paragraph."""

    if not context:
        return "No additional context provided."

    lines = [f"- {key}: {value}" for key, value in context.items()]
    return "Context:\n" + "\n".join(lines)


def build_intent_parser(model: str = "gpt-5-mini"):
    """Return a runnable that parses user intent into a structured schema."""

    settings = get_settings()
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Extract the user's scheduling intent. "
                "Fill missing fields with null and keep lists concise.",
            ),
            MessagesPlaceholder("messages"),
        ]
    )

    llm = ChatOpenAI(
        model=model,
        temperature=settings.temperature,
        max_retries=settings.max_retries,
    )
    return prompt | llm.with_structured_output(ParsedIntent)
