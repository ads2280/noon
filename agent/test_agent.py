"""Tests for the calendar agent."""

import pytest
from datetime import datetime, timedelta
from agent.main import (
    noon_graph,
    IntentClassification,
    ShowEventExtraction,
    ShowScheduleExtraction,
    CreateEventExtraction,
    UpdateEventExtraction,
    DeleteEventExtraction,
)


class TestIntentClassification:
    """Test intent classification for all request types."""

    def test_show_event_intent(self):
        """Test classification of show-event queries."""
        state = {
            "query": "Show me my dentist appointment",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "show-event"
        assert result["success"] is True
        assert "metadata" in result

    def test_show_schedule_intent(self):
        """Test classification of show-schedule queries."""
        state = {
            "query": "What am I doing tomorrow?",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "show-schedule"
        assert result["success"] is True
        assert "start-date" in result["metadata"]
        assert "end-date" in result["metadata"]

    def test_create_event_intent(self):
        """Test classification of create-event queries."""
        state = {
            "query": "Schedule a meeting with Sarah tomorrow at 2pm",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "create-event"
        assert result["success"] is True
        assert "title" in result["metadata"]

    def test_update_event_intent(self):
        """Test classification of update-event queries."""
        state = {
            "query": "Move my 3pm meeting to 4pm",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "update-event"
        assert result["success"] is True

    def test_delete_event_intent(self):
        """Test classification of delete-event queries."""
        state = {
            "query": "Cancel my meeting with John",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "delete-event"
        assert result["success"] is True

    def test_no_action_intent(self):
        """Test classification of queries that don't require calendar action."""
        state = {
            "query": "How are you doing today?",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "no-action"
        assert result["success"] is True


class TestShowSchedule:
    """Test show_schedule date parsing functionality."""

    def test_tomorrow_parsing(self):
        """Test parsing 'tomorrow' into date range."""
        state = {
            "query": "What am I doing tomorrow?",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "show-schedule"

        # Verify dates are in ISO format
        start_date = result["metadata"]["start-date"]
        end_date = result["metadata"]["end-date"]
        assert len(start_date) == 10  # YYYY-MM-DD format
        assert start_date == end_date  # Same day for tomorrow

    def test_next_week_parsing(self):
        """Test parsing 'next week' into date range."""
        state = {
            "query": "Show my schedule next week",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "show-schedule"

        start_date = result["metadata"]["start-date"]
        end_date = result["metadata"]["end-date"]

        # Next week should be a 7-day range
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        assert (end - start).days >= 6  # At least 6 days difference

    def test_specific_day_parsing(self):
        """Test parsing specific days like 'next Monday'."""
        state = {
            "query": "Am I free next Monday?",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "show-schedule"

        start_date = result["metadata"]["start-date"]
        end_date = result["metadata"]["end-date"]
        assert start_date == end_date  # Single day query

    def test_weekend_parsing(self):
        """Test parsing 'this weekend' into date range."""
        state = {
            "query": "What's on my calendar this weekend?",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "show-schedule"

        # Weekend should be 2 days (Saturday and Sunday)
        start_date = result["metadata"]["start-date"]
        end_date = result["metadata"]["end-date"]
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        assert (end - start).days <= 1  # 0 or 1 day difference


class TestCreateEvent:
    """Test create_event metadata extraction."""

    def test_basic_event_creation(self):
        """Test creating a basic event with time."""
        state = {
            "query": "Schedule a meeting with Sarah tomorrow at 2pm",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "create-event"

        metadata = result["metadata"]
        assert "title" in metadata
        assert "start-date" in metadata
        assert "end-date" in metadata
        assert (
            "sarah" in metadata["title"].lower()
            or "meeting" in metadata["title"].lower()
        )

    def test_event_with_location(self):
        """Test creating event with location."""
        state = {
            "query": "Add dentist appointment next Tuesday at 10am at 123 Main St",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "create-event"

        metadata = result["metadata"]
        assert "title" in metadata
        assert "location" in metadata
        assert "123 Main St" in metadata["location"]

    def test_event_with_attendees(self):
        """Test creating event with attendees."""
        state = {
            "query": "Create team standup Monday at 9am, invite team@company.com",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "create-event"

        metadata = result["metadata"]
        assert "title" in metadata
        assert "attendees" in metadata
        assert isinstance(metadata["attendees"], list)

    def test_event_duration(self):
        """Test that event has both start and end dates."""
        state = {
            "query": "Schedule a 2-hour workshop tomorrow at 3pm",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "create-event"

        metadata = result["metadata"]
        assert "start-date" in metadata
        assert "end-date" in metadata
        # Verify both are valid ISO format
        assert "T" in metadata["start-date"] or len(metadata["start-date"]) == 10


class TestUpdateEvent:
    """Test update_event metadata extraction."""

    def test_time_update(self):
        """Test updating event time."""
        state = {
            "query": "Move my 3pm meeting to 4pm",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "update-event"

        metadata = result["metadata"]
        assert "search-title" in metadata or "event-id" in metadata

    def test_location_update(self):
        """Test updating event location."""
        state = {
            "query": "Change the location of my dentist appointment to 456 Oak Ave",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "update-event"

        metadata = result["metadata"]
        assert "location" in metadata
        assert "456 Oak Ave" in metadata["location"]

    def test_title_update(self):
        """Test renaming an event."""
        state = {
            "query": "Rename my team meeting to 'Sprint Planning'",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "update-event"

        metadata = result["metadata"]
        assert "title" in metadata or "search-title" in metadata


class TestDeleteEvent:
    """Test delete_event metadata extraction."""

    def test_simple_deletion(self):
        """Test deleting an event by name."""
        state = {
            "query": "Cancel my meeting with John",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "delete-event"

        metadata = result["metadata"]
        assert "search-title" in metadata or "event-id" in metadata

    def test_deletion_with_time(self):
        """Test deleting an event by time reference."""
        state = {
            "query": "Delete my 3pm call",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "delete-event"

        metadata = result["metadata"]
        assert metadata is not None


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_query(self):
        """Test handling of empty query."""
        state = {
            "query": "",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        assert result["request"] == "no-action"

    def test_ambiguous_query(self):
        """Test handling of ambiguous query."""
        state = {
            "query": "meeting",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        # Should either be no-action or try to show-event/show-schedule
        assert result["request"] in ["no-action", "show-event", "show-schedule"]

    def test_multiple_events_mentioned(self):
        """Test query mentioning multiple events."""
        state = {
            "query": "Show me my dentist appointment and my meeting with John",
            "auth": {},
            "success": False,
            "request": "no-action",
            "metadata": {},
        }
        result = noon_graph.invoke(state)
        # Should classify as show-event or show-schedule
        assert result["request"] in ["show-event", "show-schedule"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
