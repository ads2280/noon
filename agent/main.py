"""Calendar scheduling agent using LangGraph and OpenAI."""

import logging
import os
from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict
from typing import Literal, Any, List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

from agent.tools import ALL_TOOLS, INTERNAL_TOOLS, EXTERNAL_TOOLS, set_auth_context

logger = logging.getLogger(__name__)

# Initialize OpenAI LLM
# ChatOpenAI will automatically read OPENAI_API_KEY from environment
# if not explicitly provided, so we don't need to pass it explicitly
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logger.warning("OPENAI_API_KEY not found in environment variables - LLM calls may fail")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.7,
    model_kwargs={"tool_choice": "required"},  # Force tool usage at model level
)

# Bind all tools to the LLM
llm_with_tools = llm.bind_tools(ALL_TOOLS)

# Create a tool lookup dictionary
TOOL_MAP = {tool.name: tool for tool in ALL_TOOLS}
INTERNAL_TOOL_NAMES = {tool.name for tool in INTERNAL_TOOLS}
EXTERNAL_TOOL_NAMES = {tool.name for tool in EXTERNAL_TOOLS}

logger.info(f"Tool mapping: {len(TOOL_MAP)} tools total")
logger.info(f"Internal tools: {INTERNAL_TOOL_NAMES}")
logger.info(f"External tools: {EXTERNAL_TOOL_NAMES}")


class State(TypedDict):
    query: str
    auth: dict
    success: bool
    type: Optional[Literal[
        "show-event",
        "show-schedule",
        "create-event",
        "update-event",
        "delete-event",
        "no-action",
    ]]
    metadata: dict[str, Any]
    messages: List[BaseMessage]
    tool_results: Dict[str, Any]
    terminated: bool
    message: Optional[str]  # For error responses
    current_time: Optional[str]  # ISO format datetime string in user's timezone with offset (e.g., "2026-01-13T08:47:00-08:00")
    timezone: Optional[str]  # IANA timezone name (e.g., "America/Los_Angeles")


class OutputState(TypedDict):
    success: bool
    type: Optional[Literal[
        "show-event",
        "show-schedule",
        "create-event",
        "update-event",
        "delete-event",
        "no-action",
    ]]
    metadata: Dict[str, Any]
    message: Optional[str]  # For error responses


def agent_node(state: State) -> Dict[str, Any]:
    """
    Main agent node that processes queries with LLM and tool calling.
    """
    query = state.get("query", "")
    messages = state.get("messages", [])
    terminated = state.get("terminated", False)
    
    logger.info(f"Agent node executed with query: {query[:50]}...")
    
    # Get time context from state
    current_time = state.get("current_time")
    user_timezone = state.get("timezone", "UTC")
    
    # Build time context string for system message
    time_context = ""
    if current_time and user_timezone:
        time_context = f"""
TIME CONTEXT:
- Current time: {current_time} (in user's timezone: {user_timezone})
- When user says "tomorrow", calculate the date based on the current date in their timezone ({user_timezone})
- When user says "next week", calculate based on the current date in their timezone
- ALWAYS use timezone-aware ISO strings with offset (e.g., "2026-01-14T00:00:00-08:00") when calling tools with datetime parameters
- The current_time is already in the user's timezone, so "tomorrow" means the next day from that time
"""
    
    # System message with strong instructions - ensure it's always first
    system_instruction = SystemMessage(content=f"""You are a calendar scheduling agent. Your job is to process user queries about their calendar and use the available tools to respond.

CRITICAL: This is a SINGLE-TURN interaction. You do NOT talk back to the user or have any back-and-forth. The user makes a request, and you call an external tool (optionally calling internal tools first to gather information), then terminate. You never respond with plain text - you always call tools.

CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE:
1. You MUST ALWAYS call at least one tool for every query. Never respond with plain text.
2. Tool calling is REQUIRED - responding without calling a tool is an error.
3. You MUST ALWAYS end with an external tool call. Internal tools gather information but do NOT complete the query.
4. ALWAYS use timezone-aware ISO strings with timezone offset when calling tools with datetime parameters.
   ✅ Correct: "2026-01-14T00:00:00-08:00" (timezone-aware with offset in user's timezone)
   ❌ Wrong: "2026-01-14T00:00:00Z" (UTC, not user timezone)
   ❌ Wrong: "2026-01-14T00:00:00" (no timezone info)

{time_context}
AGENT CYCLE OVERVIEW:
The agent follows this pattern: User Query → (Optional Internal Tools) → External Tool → Terminate

Internal tools gather information but do NOT terminate. External tools terminate the agent and show results to the user.

DECISION FLOW PATTERNS:

1. VIEW SCHEDULE
   Query intent: User wants to see their schedule for a time period
   Pattern: show_schedule(start_time, end_time)
   Example: "What is on my schedule tomorrow?" → show_schedule with 12:00 AM and 11:59 PM tomorrow

2. FIND SPECIFIC EVENT
   Query intent: User wants to know about a specific event (by name or position)
   Pattern: search_events(keywords, start_time, end_time) → EXTRACT event_id and calendar_id from results → show_event(event_id, calendar_id)
   MANDATORY: After search_events returns results, you MUST extract the event_id and calendar_id from the first matching event in the results list, then immediately call show_event with those values.
   Optional: If you need full event details, call read_event(event_id, calendar_id) before show_event
   Example: "When is my haircut this weekend?" → search_events("haircut", Saturday 12:00 AM, Sunday 11:59 PM) → extract event_id and calendar_id from first result → show_event(event_id, calendar_id)
   Example: "When is my first event tomorrow?" → read_schedule(tomorrow 12:00 AM, tomorrow 11:59 PM) → identify first event by start time → extract event_id and calendar_id → show_event(event_id, calendar_id)

3. CREATE EVENT
   Query intent: User wants to schedule/create a new event
   Pattern: read_schedule(start_time, end_time) → request_create_event(event_details, calendar_id)
   Optional: If checking for conflicts with existing events, call search_events first
   Example: "Can you schedule a haircut for me next week?" → read_schedule(Monday 12:00 AM, Friday 11:59 PM) → request_create_event with event details at a non-conflicting time

4. UPDATE EVENT
   Query intent: User wants to modify an existing event
   Pattern: search_events(keywords, start_time, end_time) → EXTRACT event_id and calendar_id from results → request_update_event(event_id, calendar_id, new_details)
   MANDATORY: After search_events returns results, you MUST extract the event_id and calendar_id from the first matching event, then call request_update_event with those values.
   Optional: If checking availability at new time, call read_schedule(new_time_window) before request_update_event
   Example: "Can you move my haircut to Thursday next week?" → search_events("haircut", Monday 12:00 AM, Friday 11:59 PM) → extract event_id and calendar_id from first result → read_schedule(Thursday 12:00 AM, Thursday 11:59 PM) → request_update_event with new Thursday time that doesn't conflict

5. DELETE EVENT
   Query intent: User wants to remove/cancel an event
   Pattern: search_events(keywords, start_time, end_time) → EXTRACT event_id and calendar_id from results → request_delete_event(event_id, calendar_id)
   MANDATORY: After search_events returns results, you MUST extract the event_id and calendar_id from the first matching event, then immediately call request_delete_event with those values.
   Example: "Can you remove my haircut this weekend?" → search_events("haircut", Saturday 12:00 AM, Sunday 11:59 PM) → extract event_id and calendar_id from first result → request_delete_event(event_id, calendar_id)

6. UNSUPPORTED REQUEST
   Query intent: Request is not a calendar operation or is unclear
   Pattern: do_nothing(reason)
   Example: "Can you book a haircut for me?" → do_nothing("unsupported request - booking requires external service")

EXAMPLE TRAJECTORIES:

1. "What is on my schedule tomorrow?"
   → show_schedule(start_time: tomorrow 12:00 AM, end_time: tomorrow 11:59 PM)

2. "When is my haircut this weekend?"
   → search_events(keywords: "haircut", start_time: Saturday 12:00 AM, end_time: Sunday 11:59 PM)
   → show_event(event_id: found_event_id, calendar_id: found_calendar_id)

3. "Can you remove my haircut this weekend?"
   → search_events(keywords: "haircut", start_time: Saturday 12:00 AM, end_time: Sunday 11:59 PM)
   → request_delete_event(event_id: found_event_id, calendar_id: found_calendar_id)

4. "Can you schedule a haircut for me next week?"
   → read_schedule(start_time: Monday 12:00 AM, end_time: Friday 11:59 PM)
   → request_create_event(summary: "haircut", start_time: available_time, end_time: available_time + duration, calendar_id: selected_calendar_id)

5. "Can you move my haircut to Thursday next week?"
   → search_events(keywords: "haircut", start_time: Monday 12:00 AM, end_time: Friday 11:59 PM)
   → read_schedule(start_time: Thursday 12:00 AM, end_time: Thursday 11:59 PM)
   → request_update_event(event_id: found_event_id, calendar_id: found_calendar_id, start_time: new_thursday_time, end_time: new_thursday_time + duration)

6. "Can you book a haircut for me?"
   → do_nothing(reason: "unsupported request")

PROCESSING TOOL RESULTS:
When internal tools return results, you MUST extract the necessary information and call an external tool:

- After search_events returns events: The results are a list of event dictionaries. Extract the 'id' field as event_id and 'calendar_id' field as calendar_id from the FIRST event in the list, then immediately call show_event(event_id, calendar_id) or request_delete_event(event_id, calendar_id) or request_update_event(event_id, calendar_id, ...) depending on the query intent.

- After read_schedule returns events: The results are a list of event dictionaries. If the query asks about a specific event (first, last, etc.), identify that event by sorting by start time, extract the 'id' field as event_id and 'calendar_id' field as calendar_id, then call show_event(event_id, calendar_id).

- After read_event returns event details: Extract the 'id' field as event_id and 'calendar_id' field as calendar_id from the result dictionary, then call show_event(event_id, calendar_id).

CRITICAL: Tool results are returned as strings containing Python list/dict representations. Parse them to extract the actual event_id and calendar_id values. Never stop after an internal tool call - always process the results and call an external tool to complete the query.

AVAILABLE TOOLS:

INTERNAL TOOLS (for gathering information - do NOT terminate):
- read_schedule(start_time, end_time): Get events in a time window
- search_events(keywords, start_time, end_time): Find events matching keywords
- read_event(event_id, calendar_id): Get full details of a specific event
- list_calendars(): List all available calendars

EXTERNAL TOOLS (terminate agent and show results to user):
- show_schedule(start_time, end_time): Display schedule to user
- show_event(event_id, calendar_id): Display specific event to user
- request_create_event(summary, start_time, end_time, calendar_id, description, location): Request to create event
- request_update_event(event_id, calendar_id, summary, start_time, end_time, description, location): Request to update event
- request_delete_event(event_id, calendar_id): Request to delete event
- do_nothing(reason): Handle unsupported/unclear requests

FINAL REMINDERS:
- ALWAYS end with an external tool call. Internal tools are for gathering information only.
- After ANY internal tool returns results, you MUST extract the necessary information (event_id, calendar_id, etc.) and call an external tool.
- When search_events or read_schedule returns a list of events, extract event_id from the 'id' field and calendar_id from the 'calendar_id' field of the relevant event.
- Calculate relative times (tomorrow, next week) based on current_time in the user's timezone.
- Use timezone-aware ISO strings with offset (e.g., "2026-01-14T00:00:00-08:00") for all datetime parameters.
- "show me my schedule" = call show_schedule. "what's on my schedule" = call show_schedule. These are NOT do_nothing cases.
- If you use read_schedule or search_events, you MUST follow up with an external tool - never stop after just an internal tool.
- When you see tool results like "[{{'id': 'event_002', 'calendar_id': 'cal_primary_123', ...}}]", extract 'event_002' as the event_id and 'cal_primary_123' as the calendar_id.""")
    
    # Initialize messages if empty
    if not messages:
        messages = [system_instruction, HumanMessage(content=query)]
    else:
        # Ensure system message is first if messages already exist
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            messages = [system_instruction] + messages
    
    try:
        # Invoke LLM with tools (tool_choice="required" set at model level)
        response = llm_with_tools.invoke(messages)
        logger.info(f"LLM response received, tool_calls: {len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0}")
        
        # Add AI message to conversation
        new_messages = messages + [response]
        
        # Check if LLM made tool calls (should always be true with tool_choice="required")
        if hasattr(response, 'tool_calls') and response.tool_calls:
            # Convert LangChain ToolCall objects to dictionaries
            # LangChain tool_calls are typically objects with .name, .args, .id attributes
            tool_calls_dict = []
            for tool_call in response.tool_calls:
                if isinstance(tool_call, dict):
                    tool_calls_dict.append(tool_call)
                else:
                    # It's a ToolCall object - extract attributes
                    tool_calls_dict.append({
                        "name": getattr(tool_call, "name", ""),
                        "args": getattr(tool_call, "args", {}),
                        "id": getattr(tool_call, "id", ""),
                    })
            
            logger.info(f"Converted {len(tool_calls_dict)} tool calls: {[tc.get('name', 'unknown') for tc in tool_calls_dict]}")
            logger.info(f"Tool calls dict structure: {tool_calls_dict}")
            # Return state with tool calls for tool execution node
            # Ensure success is True (or at least not False) so routing works correctly
            return {
                "messages": new_messages,
                "success": True,  # Set success to True so should_continue routes to tool_execution
                "tool_results": {
                    "tool_calls": tool_calls_dict,
                },
            }
        else:
            # No tool calls - this should not happen with tool_choice="required"
            # Return error instead of no-action
            logger.error("No tool calls detected despite tool_choice='required' - this is an error")
            content = response.content if hasattr(response, 'content') else str(response)
            return {
                "success": False,
                "message": f"Agent failed to call tools. LLM response: {content[:200] if content else 'No response'}",
                "terminated": True,
                "messages": new_messages,
            }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in agent node: {error_msg}", exc_info=True)
        # Return error state that will be picked up by format_response_node
        return {
            "success": False,
            "message": f"Agent error: {error_msg}",
            "terminated": True,
            "tool_results": {
                "external_tool_result": None,  # Explicitly set to None to avoid confusion
            },
        }


def tool_execution_node(state: State) -> Dict[str, Any]:
    """
    Execute tools based on LLM tool calls.
    Distinguishes between internal and external tools.
    """
    try:
        tool_results = state.get("tool_results", {})
        tool_calls = tool_results.get("tool_calls", [])
        messages = state.get("messages", [])
        auth = state.get("auth")  # Get auth from state
        
        logger.info(f"Tool execution node: executing {len(tool_calls)} tool calls")
        
        if not tool_calls:
            logger.warning("No tool calls to execute")
            return {"terminated": True}
        
        # Set auth context for tools to access
        set_auth_context(auth)
        
        tool_messages = []
        has_external_tool = False
        external_tool_result = None
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")
            
            logger.info(f"Executing tool: {tool_name} with args: {list(tool_args.keys())}")
            logger.info(f"Tool name in TOOL_MAP: {tool_name in TOOL_MAP}")
            logger.info(f"Tool name in EXTERNAL_TOOL_NAMES: {tool_name in EXTERNAL_TOOL_NAMES}")
            
            if tool_name not in TOOL_MAP:
                logger.error(f"Unknown tool: {tool_name}. Available tools: {list(TOOL_MAP.keys())}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Error: Unknown tool {tool_name}",
                        tool_call_id=tool_id,
                    )
                )
                continue
            
            try:
                # Execute the tool
                tool = TOOL_MAP[tool_name]
                result = tool.invoke(tool_args)
                logger.info(f"Tool {tool_name} executed successfully, result type: {type(result)}")
                
                # Check if this is an external tool
                if tool_name in EXTERNAL_TOOL_NAMES:
                    has_external_tool = True
                    external_tool_result = result
                    logger.info(f"External tool {tool_name} executed, result: {result}")
                    logger.info(f"External tool result type field: {result.get('type', 'MISSING')}")
                    # Don't add to messages, we'll handle it in format_response
                else:
                    # Internal tool - add result to messages
                    tool_messages.append(
                        ToolMessage(
                            content=str(result),
                            tool_call_id=tool_id,
                        )
                    )
                    logger.info(f"Internal tool {tool_name} executed, result length: {len(str(result))}")
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error executing tool {tool_name}: {error_msg}", exc_info=True)
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing {tool_name}: {error_msg}",
                        tool_call_id=tool_id,
                    )
                )
        
        # Update state
        new_messages = messages + tool_messages
        
        if has_external_tool:
            # External tool was called - terminate
            return {
                "messages": new_messages,
                "tool_results": {
                    "external_tool_result": external_tool_result,
                },
                "terminated": True,
            }
        else:
            # Only internal tools - continue agent loop
            return {
                "messages": new_messages,
                "tool_results": {},
            }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in tool_execution_node: {error_msg}", exc_info=True)
        return {
            "success": False,
            "message": f"Tool execution error: {error_msg}",
            "terminated": True,
        }


def format_response_node(state: State) -> Dict[str, Any]:
    """
    Format the final response for the frontend.
    Returns dict with type to match OutputState schema.
    Backend will pass through type to frontend.
    """
    tool_results = state.get("tool_results", {})
    external_tool_result = tool_results.get("external_tool_result")
    terminated = state.get("terminated", False)
    success = state.get("success", True)
    message = state.get("message")
    
    logger.info("Formatting response node")
    logger.info(f"State keys: {list(state.keys())}")
    logger.info(f"External tool result: {external_tool_result}")
    logger.info(f"Success: {success}, Message: {message}")
    
    # Check if we have an error
    if not success and message:
        logger.info(f"Returning error response: {message}")
        return {
            "success": False,
            "message": message,
        }
    
    # Check if we have an external tool result
    if external_tool_result:
        response_type = external_tool_result.get("type")
        metadata = external_tool_result.get("metadata", {})
        
        # Return with type to match OutputState
        response = {
            "success": True,
            "type": response_type,
            "metadata": metadata,
        }
        logger.info(f"Formatted response: {response_type}")
        return response
    
    # Fallback: should not happen if agent is working correctly
    # Return error instead of no-action
    logger.error("No external tool result and no error - this should not happen")
    return {
        "success": False,
        "message": "Agent failed to produce a valid response. No tool was called to handle the query.",
    }


def should_continue(state: State) -> str:
    """
    Determine the next node based on state.
    """
    terminated = state.get("terminated", False)
    success = state.get("success", True)
    tool_results = state.get("tool_results", {})
    tool_calls = tool_results.get("tool_calls", [])
    external_tool_result = tool_results.get("external_tool_result")
    messages = state.get("messages", [])
    
    logger.info(f"should_continue: terminated={terminated}, success={success}, tool_calls={len(tool_calls) if tool_calls else 0}, external_result={external_tool_result is not None}")
    
    # Priority 1: If external tool result exists, format the response
    if external_tool_result:
        logger.info("Routing to format_response: external_tool_result exists")
        return "format_response"
    
    # Priority 2: If there's an error (success=False and terminated), go to format_response
    if terminated and not success:
        logger.info("Routing to format_response: error state")
        return "format_response"
    
    # Priority 3: If there are tool calls, execute them
    if tool_calls:
        logger.info("Routing to tool_execution: tool calls exist")
        return "tool_execution"
    
    # Priority 4: If terminated (but no error), format response
    if terminated:
        logger.info("Routing to format_response: terminated")
        return "format_response"
    
    # Priority 5: Check if we have ToolMessages from internal tools - if so, continue to agent
    # This handles the case where internal tools returned results and we need to process them
    from langchain_core.messages import ToolMessage
    has_tool_messages = any(isinstance(msg, ToolMessage) for msg in messages)
    if has_tool_messages and not terminated:
        # Check if the last message is a ToolMessage (indicating we just got results from an internal tool)
        if messages and isinstance(messages[-1], ToolMessage):
            logger.info("Routing to agent: ToolMessage from internal tool needs processing")
            return "agent"
    
    # Default to format_response (shouldn't happen)
    logger.warning("Routing to format_response: default fallback")
    return "format_response"


# Build the LangGraph
logger.info("Building LangGraph for calendar scheduling agent")

graph_builder = StateGraph(State, output_schema=OutputState)

# Add nodes
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tool_execution", tool_execution_node)
graph_builder.add_node("format_response", format_response_node)

# Set entry point
graph_builder.set_entry_point("agent")

# Add conditional edges
graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tool_execution": "tool_execution",
        "format_response": "format_response",
    },
)

graph_builder.add_conditional_edges(
    "tool_execution",
    should_continue,
    {
        "agent": "agent",
        "format_response": "format_response",
    },
)

# Format response always goes to END
graph_builder.add_edge("format_response", END)

# Compile the graph
graph = graph_builder.compile()

# Export as noon_graph (required by langgraph.json)
noon_graph = graph

logger.info("LangGraph compilation complete")
