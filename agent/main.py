"""Calendar scheduling agent using LangGraph and OpenAI."""

import logging
import os
import time
from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict
from typing import Literal, Any, List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

from agent.tools import ALL_TOOLS, INTERNAL_TOOLS, EXTERNAL_TOOLS, set_auth_context
from agent.schemas.agent_response import ErrorResponse
from agent.validation import validate_request
from agent.timing_logger import log_step, log_start

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
    current_day_of_week: Optional[str]  # Full day name (e.g., "Monday", "Tuesday")


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
    query: str  # The transcribed text that was passed to the agent


def agent_node(state: State) -> Dict[str, Any]:
    """
    Main agent node that processes queries with LLM and tool calling.
    """
    node_start_time = time.time()
    query = state.get("query", "")
    messages = state.get("messages", [])
    terminated = state.get("terminated", False)
    
    log_start("agent_node", details=f"query_length={len(query)}")
    
    # Get time context from state
    current_time = state.get("current_time")
    user_timezone = state.get("timezone", "UTC")
    current_day_of_week = state.get("current_day_of_week")
    
    # Build time context string for system message
    time_context = ""
    if current_time and user_timezone:
        # Extract date from current_time (ISO format: YYYY-MM-DDTHH:MM:SS...)
        current_date = current_time.split("T")[0] if "T" in current_time else ""
        day_info = f"- Today is {current_day_of_week}\n" if current_day_of_week else ""
        date_info = f"- Today's date: {current_date}\n" if current_date else ""
        
        time_context = f"""
TIME CONTEXT:
- Current time: {current_time} (in user's timezone: {user_timezone})
{day_info}{date_info}
REASONING PROCESS (REQUIRED):
Before calculating any dates, you MUST follow this reasoning process:

Today is {current_day_of_week}, {current_date}.

When interpreting relative dates:
1. First identify what day/period is being referenced
2. Calculate from today's date ({current_date})
3. "Weekend" always means Saturday and Sunday
4. "This [day/weekend]" means the upcoming occurrence within this calendar week (Mon-Sun)
5. "Next [day/weekend]" means the occurrence in the following calendar week

Before providing dates, show your reasoning:
- What is today? {current_day_of_week}, {current_date}
- What period is requested? [Identify from user query]
- What are the specific dates? [Calculate and verify they match the requested period]
- Verification: For weekends, verify the dates are Saturday-Sunday. For days, verify the day name matches.

DATE PARSING:
- "tomorrow" = next day from current date
- "next week" = week starting after this weekend
- "on [day]" or "[day]" = next occurrence of that day (if before that day this week, use this week; otherwise use next week)
- "this [day]" = that day of current week (if past, use next week)
- "next [day]" = that day of next week (after this weekend)
- "this weekend" = Saturday and Sunday of current week (CRITICAL: "Weekend" ALWAYS and ONLY means Saturday and Sunday. It NEVER means Monday, Tuesday, Wednesday, Thursday, or Friday. To calculate: 1) Find the next Saturday from today. 2) Use that Saturday and the following Sunday. 3) Verify: The start date MUST be a Saturday, and the end date MUST be a Sunday. If you calculate dates that are not Saturday-Sunday, you made an error - recalculate.)
- "next weekend" = Saturday and Sunday of next week (CRITICAL: "Weekend" ALWAYS and ONLY means Saturday and Sunday. To calculate: 1) First find "this weekend" (Saturday-Sunday). 2) Add exactly 7 days to get next weekend's Saturday. 3) Next weekend's Sunday is the day after next weekend's Saturday. 4) Verify: The start date MUST be a Saturday, and the end date MUST be a Sunday. If you calculate dates that are not Saturday-Sunday, you made an error - recalculate.)

EXAMPLES (assuming today is Tuesday, December 23):
- "on Friday" = Friday, December 26 (this week)
- "next Thursday" = Thursday, January 1 (next week)
- "this Friday" = Friday, December 26 (this week)
- "this weekend" = Saturday, December 27 and Sunday, December 28 (00:00:00 Saturday to 23:59:59 Sunday) - ALWAYS Saturday-Sunday, never any other days
- "next weekend" = Saturday, January 3 and Sunday, January 4 (00:00:00 Saturday to 23:59:59 Sunday) - ALWAYS Saturday-Sunday, never any other days
- "next week" = week starting Monday, December 29

ALWAYS use timezone-aware ISO strings with offset (e.g., "2026-01-14T00:00:00-08:00") when calling tools with datetime parameters.
Calculate all relative dates based on current_time in the user's timezone ({user_timezone}).
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

CRITICAL: CALENDAR SELECTION FOR WRITE OPERATIONS:
When creating, updating, or deleting events, you MUST follow these rules:
1. ALWAYS call list_calendars() FIRST to get calendars with write permissions
2. ONLY use calendar_id values from list_calendars() results for write operations
3. NEVER use calendar_id values from event results (read_schedule, search_events, read_event) for write operations
4. Event results may include calendar_ids from read-only calendars - these are NOT valid for write operations
5. list_calendars() returns ONLY calendars with write access (access_role: "writer" or "owner")
6. When selecting a calendar, prefer the user's primary calendar (is_primary: true) if available, otherwise use any calendar from list_calendars()

DECISION FLOW PATTERNS:

1. VIEW SCHEDULE
   Query intent: User wants to see their schedule for a time period
   Pattern: show_schedule(start_time, end_time)
   Example: "What is on my schedule tomorrow?" → show_schedule with 12:00 AM and 11:59 PM tomorrow

2. FIND SPECIFIC EVENT
   Query intent: User wants to know about a specific event (by name or position)
   Pattern: search_events(keywords, start_time, end_time) → EXTRACT event_id and calendar_id from results → show_event(event_id, calendar_id)
   
   KEYWORD EXTRACTION FOR SEARCH:
   - Extract key terms from the user's query, especially names and event types
   - Remove filler words: "meeting", "with", "my", "the", "a", "an", "find", "show", etc.
   - For person names: extract just the name (e.g., "meeting with andrew" → "andrew")
   - For event types: extract the core term (e.g., "my haircut appointment" → "haircut")
   - If query mentions multiple names: try searching with both names together (e.g., "jude andrew")
   - Google Calendar search matches keywords/phrases in event titles, descriptions, and locations
   - Examples:
     * "find my meeting with andrew" → search_events("andrew", ...)
     * "when is jude and andrew meeting" → search_events("jude andrew", ...)
     * "show me my haircut" → search_events("haircut", ...)
     * "meeting with john smith" → search_events("john smith", ...)
   
   FALLBACK STRATEGIES IF INITIAL SEARCH RETURNS NO RESULTS:
   - Try broader keywords: if "andrew" doesn't work, try variations or partial matches
   - Try broader date ranges: expand the time window if the initial search was too narrow
   - Use read_schedule as fallback: if you know the date but keywords aren't matching, use read_schedule(start_time, end_time) to get all events for that time period, then manually identify the matching event by checking event summaries/descriptions
   - Example fallback flow:
     * search_events("andrew", ...) returns [] 
     * → Try search_events("jude", ...) or expand date range
     * → If still no results and date is known: read_schedule(...) → manually find event with "andrew" or "jude" in summary
   
   MANDATORY: After search_events returns results, you MUST extract the event_id and calendar_id from the first matching event in the results list, then immediately call show_event with those values.
   Optional: If you need full event details, call read_event(event_id, calendar_id) before show_event
   Example: "When is my haircut this weekend?" → search_events("haircut", Saturday 12:00 AM, Sunday 11:59 PM) → extract event_id and calendar_id from first result → show_event(event_id, calendar_id)
   Example: "When is my first event tomorrow?" → read_schedule(tomorrow 12:00 AM, tomorrow 11:59 PM) → identify first event by start time → extract event_id and calendar_id → show_event(event_id, calendar_id)

3. CREATE EVENT
   Query intent: User wants to schedule/create a new event
   Pattern: list_calendars() → read_schedule(start_time, end_time) → request_create_event(event_details, calendar_id)
   CRITICAL CALENDAR SELECTION RULES:
   - You MUST call list_calendars() FIRST to get calendars with write permissions
   - You MUST ONLY use calendar_id values from list_calendars() results for create/update/delete operations
   - You MUST NOT use calendar_id values from event results (read_schedule, search_events, read_event) for write operations
   - Event results may include calendar_ids from read-only calendars - these are NOT valid for write operations
   - list_calendars() returns ONLY calendars with write access (access_role: "writer" or "owner")
   - When selecting a calendar, prefer the user's primary calendar (is_primary: true) if available, otherwise use any calendar from list_calendars()
   Optional: If checking for conflicts with existing events, call search_events first
   CRITICAL: Only include description parameter if:
   - The user explicitly mentions wanting a description (e.g., "with a note about...", "with description...")
   - The description is necessary for clarity (e.g., meeting agenda, important context)
   - Do NOT add descriptions automatically or make them up - most events don't need descriptions
   VALIDATION: After calling request_create_event, the request is validated. If validation fails (e.g., calendar is read-only), you will receive a validation error message. In this case:
   - Call list_calendars() to find calendars with write access
   - Select a different calendar with write permissions (access_role should be "writer" or "owner")
   - Retry request_create_event with the new calendar_id
   Example: "Can you schedule a haircut for me next week?" → list_calendars() → read_schedule(Monday 12:00 AM, Friday 11:59 PM) → request_create_event(summary: "haircut", start_time: available_time, end_time: available_time + duration, calendar_id: selected_from_list_calendars) - NO description parameter
   Example: "Schedule a team meeting next Tuesday with description 'Discuss Q1 goals'" → list_calendars() → request_create_event(..., description: "Discuss Q1 goals", calendar_id: selected_from_list_calendars)

4. UPDATE EVENT
   Query intent: User wants to modify an existing event
   Pattern: search_events(keywords, start_time, end_time) → EXTRACT event_id and calendar_id from results → request_update_event(event_id, calendar_id, new_details)
   MANDATORY: After search_events returns results, you MUST extract the event_id and calendar_id from the first matching event, then call request_update_event with those values.
   Optional: If checking availability at new time, call read_schedule(new_time_window) before request_update_event
   CRITICAL: Only include description parameter if:
   - The user explicitly mentions updating or adding a description
   - Do NOT add or modify descriptions automatically or make them up
   - Only update the fields the user explicitly mentions changing
   VALIDATION: After calling request_update_event, the request is validated. If validation fails (e.g., calendar is read-only), you will receive a validation error message. In this case:
   - Call list_calendars() to find calendars with write access
   - Note: You cannot change the calendar_id for an existing event, but you can inform the user about the limitation
   Example: "Can you move my haircut to Thursday next week?" → search_events("haircut", Monday 12:00 AM, Friday 11:59 PM) → extract event_id and calendar_id from first result → read_schedule(Thursday 12:00 AM, Thursday 11:59 PM) → request_update_event(event_id, calendar_id, start_time: new_thursday_time, end_time: new_thursday_time + duration) - NO description parameter

5. DELETE EVENT
   Query intent: User wants to remove/cancel an event
   Pattern: search_events(keywords, start_time, end_time) → EXTRACT event_id and calendar_id from results → request_delete_event(event_id, calendar_id)
   MANDATORY: After search_events returns results, you MUST extract the event_id and calendar_id from the first matching event, then immediately call request_delete_event with those values.
   VALIDATION: After calling request_delete_event, the request is validated. If validation fails (e.g., calendar is read-only), you will receive a validation error message. In this case:
   - You cannot delete events from read-only calendars - inform the user about this limitation
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
   → list_calendars() → read_schedule(start_time: Monday 12:00 AM, end_time: Friday 11:59 PM)
   → request_create_event(summary: "haircut", start_time: available_time, end_time: available_time + duration, calendar_id: selected_from_list_calendars)

5. "Can you move my haircut to Thursday next week?"
   → search_events(keywords: "haircut", start_time: Monday 12:00 AM, end_time: Friday 11:59 PM)
   → read_schedule(start_time: Thursday 12:00 AM, end_time: Thursday 11:59 PM)
   → request_update_event(event_id: found_event_id, calendar_id: found_calendar_id, start_time: new_thursday_time, end_time: new_thursday_time + duration)

6. "Can you book a haircut for me?"
   → do_nothing(reason: "unsupported request")

7. "Show me my schedule on Friday"
   → show_schedule(start_time: Friday 12:00 AM, end_time: Friday 11:59 PM)
   Note: If today is before Friday, use this week's Friday; if today is Friday or after, use next week's Friday

8. "What's on my calendar next Thursday?"
   → show_schedule(start_time: next Thursday 12:00 AM, end_time: next Thursday 11:59 PM)
   Note: "next Thursday" means Thursday of next week (after this weekend)

9. "Show me this weekend"
   → show_schedule(start_time: Saturday 00:00:00, end_time: Sunday 23:59:59)
   CRITICAL: Weekend means Saturday-Sunday ONLY. Find the next Saturday from today, then use that Saturday and the following Sunday. Verify the dates are Saturday-Sunday before calling the tool.

10. "What's on my calendar next weekend?"
   → show_schedule(start_time: next weekend Saturday 00:00:00, end_time: next weekend Sunday 23:59:59)
   CRITICAL: Weekend means Saturday-Sunday ONLY. Calculate this weekend first, then add 7 days to get next weekend's Saturday. Verify the dates are Saturday-Sunday before calling the tool.

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
- request_create_event(summary, start_time, end_time, calendar_id, description=None, location=None): Request to create event. Only include description/location if explicitly requested or necessary.
- request_update_event(event_id, calendar_id, summary=None, start_time=None, end_time=None, description=None, location=None): Request to update event. Only include fields that need updating. Only include description if explicitly requested.
- request_delete_event(event_id, calendar_id): Request to delete event
- do_nothing(reason): Handle unsupported/unclear requests

VALIDATION ERRORS:
- If you receive a validation error after calling request_create_event, request_update_event, or request_delete_event:
  - The error message will explain the issue (e.g., "Calendar is read-only")
  - For create operations: Call list_calendars() to find a calendar with write access (access_role should be "writer" or "owner") and retry
  - For update/delete operations: You cannot change the calendar for an existing event - inform the user about the limitation
  - Always retry with the corrected information when validation errors occur

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
        llm_start_time = time.time()
        response = llm_with_tools.invoke(messages)
        llm_duration = time.time() - llm_start_time
        tool_call_count = len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0
        log_step("agent_node.llm_invoke", llm_duration, details=f"tool_calls={tool_call_count}")
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
            node_duration = time.time() - node_start_time
            tool_names = [tc.get('name', 'unknown') for tc in tool_calls_dict]
            log_step("agent_node", node_duration, details=f"tools={tool_names}")
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
            node_duration = time.time() - node_start_time
            log_step("agent_node", node_duration, details="error=no_tool_calls")
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
        node_duration = time.time() - node_start_time
        log_step("agent_node", node_duration, details=f"ERROR: {error_msg[:100]}")
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
    node_start_time = time.time()
    try:
        tool_results = state.get("tool_results", {})
        tool_calls = tool_results.get("tool_calls", [])
        messages = state.get("messages", [])
        auth = state.get("auth")  # Get auth from state
        
        log_start("tool_execution_node", details=f"tool_count={len(tool_calls)}")
        
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
                tool_start_time = time.time()
                result = tool.invoke(tool_args)
                tool_duration = time.time() - tool_start_time
                log_step(f"tool_execution_node.tool.{tool_name}", tool_duration)
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
        
        node_duration = time.time() - node_start_time
        if has_external_tool:
            # External tool was called - DON'T terminate yet, let validation_node decide
            # Validation will run before termination
            log_step("tool_execution_node", node_duration, details="external tool executed")
            return {
                "messages": new_messages,
                "tool_results": {
                    "external_tool_result": external_tool_result,
                },
                "terminated": False,  # Don't terminate yet - validation will decide
            }
        else:
            # Only internal tools - continue agent loop
            log_step("tool_execution_node", node_duration, details="result=internal_tools_only")
            return {
                "messages": new_messages,
                "tool_results": {},
            }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in tool_execution_node: {error_msg}", exc_info=True)
        node_duration = time.time() - node_start_time
        log_step("tool_execution_node", node_duration, details=f"ERROR: {error_msg[:100]}")
        return {
            "success": False,
            "message": f"Tool execution error: {error_msg}",
            "terminated": True,
        }


def validation_node(state: State) -> Dict[str, Any]:
    """
    Validate external tool results before termination.
    
    If validation fails, return error as ToolMessage to agent loop so it can retry.
    If validation passes, proceed to format_response.
    """
    node_start_time = time.time()
    try:
        tool_results = state.get("tool_results", {})
        external_tool_result = tool_results.get("external_tool_result")
        messages = state.get("messages", [])
        auth = state.get("auth")
        
        log_start("validation_node")
        
        # If no external tool result, nothing to validate - proceed
        if not external_tool_result:
            logger.info("No external tool result to validate - proceeding")
            node_duration = time.time() - node_start_time
            log_step("validation_node", node_duration, details="result=no_external_tool")
            return {
                "terminated": True,
            }
        
        # Extract request type from external tool result
        result_type = external_tool_result.get("type")
        logger.info(f"Validating request type: {result_type}")
        
        # Validate the request
        validate_start_time = time.time()
        validation_error = validate_request(external_tool_result, auth)
        validate_duration = time.time() - validate_start_time
        log_step("validation_node.validate_request", validate_duration)
        
        if validation_error:
            # Validation failed - return error to agent loop
            logger.info(f"Validation failed: {validation_error}")
            
            # Convert validation error to ToolMessage
            # We need to find the last AIMessage with tool_calls to attach this error
            tool_message = None
            for msg in reversed(messages):
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    # Use the first tool_call_id from the last tool-calling message
                    tool_call_id = msg.tool_calls[0].get("id", "") if isinstance(msg.tool_calls[0], dict) else getattr(msg.tool_calls[0], "id", "")
                    if tool_call_id:
                        tool_message = ToolMessage(
                            content=validation_error,
                            tool_call_id=tool_call_id,
                        )
                        break
            
            # If we couldn't find a tool_call_id, create a generic ToolMessage
            if not tool_message:
                tool_message = ToolMessage(
                    content=validation_error,
                    tool_call_id="validation-error",
                )
            
            # Clear external_tool_result and set terminated to False to continue agent loop
            new_messages = messages + [tool_message]
            node_duration = time.time() - node_start_time
            log_step("validation_node", node_duration, details="FAILED")
            return {
                "messages": new_messages,
                "tool_results": {},  # Clear external_tool_result
                "terminated": False,  # Continue agent loop
            }
        else:
            # Validation passed - proceed to format_response
            # Keep external_tool_result and terminated=True so format_response can use it
            logger.info("Validation passed - proceeding to format_response")
            node_duration = time.time() - node_start_time
            log_step("validation_node", node_duration, details="result=validation_passed")
            return {
                "tool_results": {
                    "external_tool_result": external_tool_result,  # Preserve for format_response
                },
                "terminated": True,  # Proceed to format_response
            }
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in validation_node: {error_msg}", exc_info=True)
        # On validation node error, fail safe - proceed to format_response
        # (better to let the request through than block everything)
        node_duration = time.time() - node_start_time
        log_step("validation_node", node_duration, details=f"ERROR: {error_msg[:100]}")
        return {
            "terminated": True,
        }


def format_response_node(state: State) -> Dict[str, Any]:
    """
    Format the final response for the frontend.
    Returns dict with type to match OutputState schema.
    Backend will pass through type to frontend.
    """
    node_start_time = time.time()
    tool_results = state.get("tool_results", {})
    external_tool_result = tool_results.get("external_tool_result")
    terminated = state.get("terminated", False)
    success = state.get("success", True)
    message = state.get("message")
    query = state.get("query", "")
    
    log_start("format_response_node")
    logger.info(f"State keys: {list(state.keys())}")
    logger.info(f"Query from state: {query}")
    logger.info(f"External tool result: {external_tool_result}")
    logger.info(f"Success: {success}, Message: {message}")
    
    # Check if we have an error
    if not success and message:
        logger.info(f"Returning error response: {message}")
        error_response = ErrorResponse(message=message, query=query)
        node_duration = time.time() - node_start_time
        log_step("format_response_node", node_duration, details="result=error")
        return error_response.model_dump()
    
    # Check if we have an external tool result
    # Tools now return properly formatted response dicts via .model_dump()
    # which already include success, type, and metadata fields
    if external_tool_result:
        response_type = external_tool_result.get("type")
        logger.info(f"Formatted response: {response_type}")
        # Add query to the external tool result dict
        external_tool_result["query"] = query
        node_duration = time.time() - node_start_time
        log_step("format_response_node", node_duration, details=f"type: {response_type}")
        return external_tool_result
    
    # Fallback: should not happen if agent is working correctly
    # Return error instead of no-action
    logger.error("No external tool result and no error - this should not happen")
    error_response = ErrorResponse(
        message="Agent failed to produce a valid response. No tool was called to handle the query.",
        query=query
    )
    node_duration = time.time() - node_start_time
    log_step("format_response_node", node_duration, details="result=fallback_error")
    return error_response.model_dump()


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
    
    # Priority 1: If external tool result exists and we haven't validated yet, go to validation
    # Check if we're coming from tool_execution with an external_tool_result
    if external_tool_result and not terminated:
        logger.info("Routing to validation: external_tool_result exists, needs validation")
        return "validation"
    
    # Priority 2: If external tool result exists after validation (terminated=True), format the response
    if external_tool_result and terminated:
        logger.info("Routing to format_response: external_tool_result validated and ready")
        return "format_response"
    
    # Priority 3: If there's an error (success=False and terminated), go to format_response
    if terminated and not success:
        logger.info("Routing to format_response: error state")
        return "format_response"
    
    # Priority 4: If there are tool calls, execute them
    if tool_calls:
        logger.info("Routing to tool_execution: tool calls exist")
        return "tool_execution"
    
    # Priority 5: If terminated (but no error), format response
    if terminated:
        logger.info("Routing to format_response: terminated")
        return "format_response"
    
    # Priority 6: Check if we have ToolMessages from internal tools or validation errors - if so, continue to agent
    # This handles the case where internal tools returned results or validation failed and we need to process them
    from langchain_core.messages import ToolMessage
    has_tool_messages = any(isinstance(msg, ToolMessage) for msg in messages)
    if has_tool_messages and not terminated:
        # Check if the last message is a ToolMessage (indicating we just got results from an internal tool or validation error)
        if messages and isinstance(messages[-1], ToolMessage):
            logger.info("Routing to agent: ToolMessage from internal tool or validation error needs processing")
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
graph_builder.add_node("validation", validation_node)
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
        "validation": "validation",  # New validation step for external tools
        "agent": "agent",
        "format_response": "format_response",
    },
)

graph_builder.add_conditional_edges(
    "validation",
    should_continue,
    {
        "agent": "agent",  # Validation failed, retry
        "format_response": "format_response",  # Validation passed
    },
)

# Format response always goes to END
graph_builder.add_edge("format_response", END)

# Compile the graph
graph = graph_builder.compile()

# Export as noon_graph (required by langgraph.json)
noon_graph = graph

logger.info("LangGraph compilation complete")
