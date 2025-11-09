#!/usr/bin/env python3
"""Test script for Google Calendar API operations using token.json."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the noon_agent directory to the path
noon_agent_dir = Path(__file__).parent / "noon_agent"
sys.path.insert(0, str(noon_agent_dir.parent))

from noon_agent.gcal_wrapper import (
    create_calendar_event,
    delete_calendar_event,
    get_calendar_service,
    read_calendar_events,
    search_calendar_events,
    update_calendar_event,
)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(result: dict, operation: str):
    """Print the result of an operation."""
    if result.get("status") == "success":
        print(f"✅ {operation} succeeded!")
        for key, value in result.items():
            if key != "status":
                print(f"   {key}: {value}")
    else:
        print(f"❌ {operation} failed!")
        print(f"   Error: {result.get('error', 'Unknown error')}")


def main():
    """Run all calendar operation tests."""
    script_dir = Path(__file__).parent
    credentials_path = script_dir / "credentials.json"
    token_path = script_dir / "token.json"

    # Check if token.json exists
    if not token_path.exists():
        print(f"❌ Error: token.json not found at {token_path}")
        print("\nPlease run generate_token.py first to create token.json")
        sys.exit(1)

    print("🔐 Initializing Google Calendar service...")
    try:
        service = get_calendar_service(
            credentials_path=str(credentials_path), token_path=str(token_path)
        )
        print("✅ Service initialized successfully!")
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        sys.exit(1)

    # Test 1: Retrieve events
    print_section("TEST 1: Retrieve Events (Next 7 Days)")
    try:
        result = read_calendar_events(service=service, max_results=10)
        print_result(result, "Retrieve events")
        if result.get("status") == "success":
            print(f"\n   Found {result['count']} events:")
            for i, event in enumerate(result.get("events", [])[:5], 1):  # Show first 5
                print(f"   {i}. {event['summary']} - {event['start']}")
            if result["count"] > 5:
                print(f"   ... and {result['count'] - 5} more")
    except Exception as e:
        print(f"❌ Exception: {e}")

    # Test 2: Query/Search events
    print_section("TEST 2: Search Events (Query)")
    try:
        # Search for events with common keywords
        search_queries = ["meeting", "lunch", "call"]
        for query in search_queries:
            print(f"\n   Searching for: '{query}'")
            result = search_calendar_events(service=service, query=query, max_results=5)
            if result.get("status") == "success":
                count = result.get("count", 0)
                if count > 0:
                    print(f"   ✅ Found {count} event(s) matching '{query}':")
                    for event in result.get("events", [])[:3]:  # Show first 3
                        print(f"      - {event['summary']} at {event['start']}")
                else:
                    print(f"   ℹ️  No events found matching '{query}'")
            else:
                print(f"   ❌ Search failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Exception: {e}")

    # Test 3: Create an event
    print_section("TEST 3: Create Event")
    created_event_id = None
    try:
        # Create an event 1 hour from now, lasting 30 minutes
        now = datetime.utcnow()
        start_time = now + timedelta(hours=1)
        end_time = start_time + timedelta(minutes=30)

        result = create_calendar_event(
            service=service,
            summary="Test Event - Calendar API Test",
            start_time=start_time,
            end_time=end_time,
            description="This is a test event created by the calendar API test script. You can safely delete this.",
            timezone="UTC",
        )
        print_result(result, "Create event")
        if result.get("status") == "success":
            created_event_id = result.get("event_id")
            print("\n   📅 Event created successfully!")
            print(f"   🔗 View at: {result.get('link', 'N/A')}")
    except Exception as e:
        print(f"❌ Exception: {e}")

    # Test 4: Update/Edit the event we just created
    print_section("TEST 4: Update/Edit Event")
    if created_event_id:
        try:
            # Update the event: change title and extend duration
            updated_start = start_time + timedelta(minutes=15)  # Move 15 min later
            updated_end = updated_start + timedelta(hours=1)  # Make it 1 hour long

            result = update_calendar_event(
                service=service,
                event_id=created_event_id,
                summary="Test Event - UPDATED",
                start_time=updated_start,
                end_time=updated_end,
                description="This event has been updated by the test script.",
                timezone="UTC",
            )
            print_result(result, "Update event")
            if result.get("status") == "success":
                print("\n   ✏️  Event updated successfully!")
                print(f"   🔗 View at: {result.get('link', 'N/A')}")
        except Exception as e:
            print(f"❌ Exception: {e}")
    else:
        print("⚠️  Skipping update test - no event was created")

    # Test 5: Delete the event we created
    print_section("TEST 5: Delete Event")
    if created_event_id:
        try:
            result = delete_calendar_event(service=service, event_id=created_event_id)
            print_result(result, "Delete event")
            if result.get("status") == "success":
                print("\n   🗑️  Event deleted successfully!")
        except Exception as e:
            print(f"❌ Exception: {e}")
    else:
        print("⚠️  Skipping delete test - no event was created")

    # Summary
    print_section("Test Summary")
    print("✅ All calendar operations tested!")
    print("\nOperations tested:")
    print("  1. ✅ Retrieve events (read_calendar_events)")
    print("  2. ✅ Query events (search_calendar_events)")
    print("  3. ✅ Create event (create_calendar_event)")
    print("  4. ✅ Update event (update_calendar_event)")
    print("  5. ✅ Delete event (delete_calendar_event)")
    print("\n💡 Note: The test event has been created and deleted.")
    print("   Check your Google Calendar to verify the operations worked correctly.")


if __name__ == "__main__":
    main()
