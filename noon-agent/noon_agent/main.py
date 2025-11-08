"""LangGraph entrypoints for the Noon agent (legacy - deprecated)."""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .config import AgentSettings, get_settings
from .helpers import build_context_block, build_prompt
from .mocks import clock_tool, ping_tool
from .schemas import AgentState


def _make_model(settings: AgentSettings) -> BaseChatModel:
    """Lazy construct the model with the project's defaults."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    return ChatOpenAI(
        model=settings.model,
        temperature=settings.temperature,
        max_retries=settings.max_retries,
        api_key=settings.openai_api_key,
    )


def _route_after_agent(state: AgentState) -> str:
    """Decide whether to call a tool or finish the run."""
    messages: List[BaseMessage] = state["messages"]
    if not messages:
        return END

    last = messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def build_agent_graph(
    settings: AgentSettings | None = None, llm: BaseChatModel | None = None
):
    """
    Create and compile the LangGraph agent (legacy version).

    DEPRECATED: Use build_calendar_graph() for the new calendar agent.
    """
    resolved_settings = settings or get_settings()
    active_llm = llm or _make_model(resolved_settings)

    tools = [
        StructuredTool.from_function(ping_tool, name="ping", description="Health-check tool."),
        StructuredTool.from_function(
            clock_tool, name="clock", description="Return the current UTC timestamp."
        ),
    ]
    tool_node = ToolNode(tools=tools)

    prompt = build_prompt()
    chain = prompt | active_llm.bind(tools=tools)

    def agent_node(state: AgentState) -> Dict[str, List[BaseMessage]]:
        response = chain.invoke({"messages": state["messages"]})
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        _route_after_agent,
        {
            "tools": "tools",
            END: END,
        },
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


def invoke_agent(
    payload: Dict[str, Any],
    settings: AgentSettings | None = None,
    llm: BaseChatModel | None = None,
) -> Any:
    """
    Convenience helper to invoke the compiled graph (legacy version).

    DEPRECATED: Use invoke_calendar_agent() for the new calendar agent.
    """
    query = payload.get("query", "").strip()
    if not query:
        raise ValueError("A query is required to run the agent.")

    context = payload.get("context") or {}
    context_block = build_context_block(context)
    composed_prompt = f"{query}\n\n{context_block}"

    initial_state: AgentState = {
        "messages": [HumanMessage(content=composed_prompt)],
        "context": context,
    }

    graph = build_agent_graph(settings=settings, llm=llm)
    return graph.invoke(initial_state)




# other ideas
# • - search_free_time – scan attendee calendars for the
#     earliest mutually available windows.
#   - propose_slots – generate a ranked shortlist
#     of candidate start/end times (with time‑zone
#     normalization).
#   - adjust_event – move an existing event by
#     ±N minutes/hours while keeping participant
#     constraints intact.
#   - sync_external – pull in events from external
#     sources (invites, shared calendars) and reconcile
#     duplicates.
#   - notify_attendees – draft/send updates or reminders
#     when an event is created, moved, or canceled.
#   - summarize_day – return a natural-language rundown
#     of the user’s schedule, conflicts, and gaps.
#   - set_preferences – store user defaults (meeting
#     lengths, working hours, buffer rules) for
#     downstream actions.
#   - resolve_conflict – pick which overlapping event
#     to keep, reschedule, or decline based on priority
#     rules.
#   - collect_requirements – gather missing metadata
#     (agenda, location, video link) before finalizing
#     an event.