"""Example usage of the Noon calendar agent."""

from datetime import datetime

from noon_agent import invoke_agent
from noon_agent.gcal_auth import get_calendar_service_from_file
from noon_agent.tools.context_tools import load_user_context


def main():
    """Demonstrate how to call the single-endpoint agent."""

    service = get_calendar_service_from_file("credentials.json", "token.json")
    user_context = load_user_context(
        service=service, user_id="user123", timezone="America/Los_Angeles"
    )
    user_context["access_token"] = "ya29...."  # Replace with a real OAuth token

    payload = {
        "query": "Schedule a meeting with Alice tomorrow at 2pm",
        "auth_token": user_context.get("access_token"),
        "calendar_id": user_context.get("primary_calendar_id", "primary"),
        "context": {
            "timezone": user_context.get("timezone", "UTC"),
            "request_time": datetime.now().isoformat(),
        },
    }

    response = invoke_agent(payload)
    print(response)


if __name__ == "__main__":
    main()
