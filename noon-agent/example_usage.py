"""Example usage of the Noon calendar agent."""

from datetime import datetime

from noon_agent import invoke_calendar_agent
from noon_agent.tools.context_tools import load_user_context
from noon_agent.gcal_auth import get_calendar_service_from_file


def main():
    """
    Example showing how to use the Noon calendar agent.

    Prerequisites:
    1. Set up Google Calendar API credentials (credentials.json)
    2. Run OAuth flow to get token.json
    3. Set OPENAI_API_KEY in .env file
    """

    # For development: Use credentials file
    # In production: You'd get the access_token from your API request
    service = get_calendar_service_from_file(
        credentials_path="credentials.json", token_path="token.json"
    )

    # Load user context (in production, this would come from your database)
    user_context = load_user_context(
        service=service, user_id="user123", timezone="America/Los_Angeles"
    )

    # Add access token to context
    # In production, this comes from the authenticated request
    user_context["access_token"] = "your-access-token-here"

    # Example 1: Create an event
    print("\n=== Example 1: Create Event ===")
    result = invoke_calendar_agent(
        user_input="Schedule a meeting with the team tomorrow at 2pm for 1 hour",
        user_context=user_context,
        current_time=datetime.now(),
    )
    print(f"Intent: {result['intent']}")
    print(f"Response: {result['response']}")

    # Example 2: Check availability
    print("\n=== Example 2: Check Availability ===")
    result = invoke_calendar_agent(
        user_input="When am I free tomorrow?",
        user_context=user_context,
        current_time=datetime.now(),
    )
    print(f"Intent: {result['intent']}")
    print(f"Response: {result['response']}")

    # Example 3: Search events
    print("\n=== Example 3: Search Events ===")
    result = invoke_calendar_agent(
        user_input="Find all my meetings about the Q4 review",
        user_context=user_context,
        current_time=datetime.now(),
    )
    print(f"Intent: {result['intent']}")
    print(f"Response: {result['response']}")

    # Example 4: Find overlap with friends
    print("\n=== Example 4: Find Mutual Availability ===")
    result = invoke_calendar_agent(
        user_input="When can Alice, Bob, and I meet next week?",
        user_context=user_context,
        current_time=datetime.now(),
    )
    print(f"Intent: {result['intent']}")
    print(f"Response: {result['response']}")

    # Example 5: Get schedule
    print("\n=== Example 5: View Schedule ===")
    result = invoke_calendar_agent(
        user_input="Show me my schedule for next week",
        user_context=user_context,
        current_time=datetime.now(),
    )
    print(f"Intent: {result['intent']}")
    print(f"Response: {result['response']}")


if __name__ == "__main__":
    main()
