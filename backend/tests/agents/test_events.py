"""Tests for conversation events."""

import datetime
from typing import Any

from devboard.agents.events import (
    SystemEvent,
    SystemEventType,
    TextMessage,
)


class TestSystemEvent:
    """Tests for SystemEvent."""

    def test_system_event_creation(self):
        """Test creating a SystemEvent for task update."""
        event = SystemEvent(
            event_type="system",
            type=SystemEventType.TASK_UPDATED,
            data={"task_id": 123, "updated_fields": {"status": "planning"}},
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )

        assert event.event_type == "system"
        assert event.type == SystemEventType.TASK_UPDATED
        assert event.data["task_id"] == 123
        assert event.data["updated_fields"]["status"] == "planning"
        assert event.timestamp == datetime.datetime(2024, 1, 1, 0, 0, 0)

    def test_system_event_without_data(self):
        """Test creating a SystemEvent without data."""
        event = SystemEvent(
            event_type="system",
            type=SystemEventType.CONVERSATION_UPDATED,
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )

        assert event.event_type == "system"
        assert event.type == SystemEventType.CONVERSATION_UPDATED
        assert event.data is None

    def test_system_event_serialization(self):
        """Test SystemEvent can be serialized to JSON."""
        event = SystemEvent(
            event_type="system",
            type=SystemEventType.TASK_UPDATED,
            data={"task_id": 456, "updated_fields": {"implementation_plan_id": 789, "status": "implementing"}},
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )

        # Serialize to dict (JSON-compatible)
        event_dict = event.model_dump(mode="json")

        assert event_dict["event_type"] == "system"
        assert event_dict["type"] == "task_updated"
        assert event_dict["data"]["task_id"] == 456
        assert event_dict["data"]["updated_fields"]["implementation_plan_id"] == 789
        assert event_dict["data"]["updated_fields"]["status"] == "implementing"
        assert event_dict["timestamp"] == "2024-01-01T00:00:00"

    def test_system_event_deserialization(self):
        """Test SystemEvent can be deserialized from JSON."""
        event_data = {
            "event_type": "system",
            "type": "conversation_updated",
            "data": {"conversation_id": 789, "updated_fields": {"external_session_id": "abc123"}},
            "timestamp": "2024-01-01T00:00:00",
        }

        event = SystemEvent.model_validate(event_data)

        assert event.event_type == "system"
        assert event.type == SystemEventType.CONVERSATION_UPDATED
        assert event.data["conversation_id"] == 789
        assert event.data["updated_fields"]["external_session_id"] == "abc123"


class TestConversationEventUnion:
    """Tests for ConversationEvent union type."""

    def test_conversation_event_discriminates_system_event(self):
        """Test that ConversationEvent union properly discriminates SystemEvent."""
        events: list[dict[str, Any]] = [
            {
                "event_type": "message",
                "role": "user",
                "text_content": "Hello",
                "timestamp": "2024-01-01T00:00:00",
            },
            {
                "event_type": "system",
                "type": "task_updated",
                "data": {"task_id": 123, "updated_fields": {"status": "planning"}},
                "timestamp": "2024-01-01T00:00:00",
            },
        ]

        # Parse events using the discriminated union
        for event_data in events:
            # This should work with the discriminator
            if event_data["event_type"] == "message":
                event = TextMessage.model_validate(event_data)
                assert isinstance(event, TextMessage)
            elif event_data["event_type"] == "system":
                event = SystemEvent.model_validate(event_data)
                assert isinstance(event, SystemEvent)
