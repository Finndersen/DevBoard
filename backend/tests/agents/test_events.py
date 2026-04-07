"""Tests for conversation events."""

import datetime
from typing import Any

from devboard.agents.events import (
    ContextUsage,
    ExecutionCompleteEvent,
    MessageRole,
    SystemEvent,
    SystemEventType,
    TextMessage,
    ToolCallRequest,
    describe_event,
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


class TestTextMessageModelField:
    """Tests for model field on TextMessage."""

    def test_model_field_default_is_none(self):
        """TextMessage.model defaults to None for backward compatibility."""
        event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        assert event.model is None

    def test_model_field_can_be_set(self):
        """TextMessage.model can be set to a model name."""
        event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
            model="claude-sonnet-4-20250514",
        )
        assert event.model == "claude-sonnet-4-20250514"

    def test_model_field_serialized(self):
        """TextMessage.model is included in serialized output."""
        event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
            model="claude-sonnet-4-20250514",
        )
        data = event.model_dump(mode="json")
        assert data["model"] == "claude-sonnet-4-20250514"

    def test_model_field_none_serialized(self):
        """TextMessage.model=None is included as null in serialized output."""
        event = TextMessage(
            role=MessageRole.AGENT,
            text_content="Hello",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        data = event.model_dump(mode="json")
        assert data["model"] is None


class TestContextUsage:
    """Tests for ContextUsage model."""

    def test_context_usage_creation(self):
        usage = ContextUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=5000,
            cache_write_tokens=1000,
        )
        assert usage.input_tokens == 100
        assert usage.output_tokens == 200
        assert usage.cache_read_tokens == 5000
        assert usage.cache_write_tokens == 1000
        assert usage.cost_usd is None

    def test_context_usage_with_cost(self):
        usage = ContextUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=5000,
            cache_write_tokens=1000,
            cost_usd=0.0123,
        )
        assert usage.cost_usd == 0.0123

    def test_context_usage_serialization(self):
        usage = ContextUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=5000,
            cache_write_tokens=1000,
            cost_usd=0.05,
        )
        data = usage.model_dump(mode="json")
        assert data["input_tokens"] == 100
        assert data["output_tokens"] == 200
        assert data["cache_read_tokens"] == 5000
        assert data["cache_write_tokens"] == 1000
        assert data["cost_usd"] == 0.05

    def test_context_usage_deserialization(self):
        data = {
            "input_tokens": 50,
            "output_tokens": 150,
            "cache_read_tokens": 3000,
            "cache_write_tokens": 500,
        }
        usage = ContextUsage.model_validate(data)
        assert usage.input_tokens == 50
        assert usage.cost_usd is None


class TestExecutionCompleteEvent:
    """Tests for ExecutionCompleteEvent with usage field."""

    def test_execution_complete_without_usage(self):
        event = ExecutionCompleteEvent(
            status="completed",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        assert event.usage is None
        assert event.status == "completed"

    def test_execution_complete_with_usage(self):
        usage = ContextUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=5000,
            cache_write_tokens=1000,
        )
        event = ExecutionCompleteEvent(
            status="completed",
            usage=usage,
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        assert event.usage is not None
        assert event.usage.input_tokens == 100
        assert event.usage.cache_read_tokens == 5000

    def test_execution_complete_serialization_without_usage(self):
        event = ExecutionCompleteEvent(
            status="failed",
            error="Something went wrong",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        data = event.model_dump(mode="json")
        assert data["event_type"] == "execution_complete"
        assert data["status"] == "failed"
        assert data["usage"] is None

    def test_execution_complete_serialization_with_usage(self):
        usage = ContextUsage(
            input_tokens=100,
            output_tokens=200,
            cache_read_tokens=5000,
            cache_write_tokens=1000,
            cost_usd=0.01,
        )
        event = ExecutionCompleteEvent(
            status="completed",
            usage=usage,
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        data = event.model_dump(mode="json")
        assert data["usage"]["input_tokens"] == 100
        assert data["usage"]["cache_read_tokens"] == 5000
        assert data["usage"]["cost_usd"] == 0.01


class TestDescribeEventWithUsage:
    """Tests for describe_event with ExecutionCompleteEvent usage."""

    def test_describe_execution_complete_without_usage(self):
        event = ExecutionCompleteEvent(
            status="completed",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        description = describe_event(event)
        assert description == "ExecutionCompleteEvent(status=completed)"

    def test_describe_execution_complete_with_usage(self):
        usage = ContextUsage(
            input_tokens=400,
            output_tokens=200,
            cache_read_tokens=5000,
            cache_write_tokens=1000,
        )
        event = ExecutionCompleteEvent(
            status="completed",
            usage=usage,
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        description = describe_event(event)
        # total_ctx = 400 + 5000 + 1000 = 6400
        assert description == "ExecutionCompleteEvent(status=completed, ctx=6,400 tokens)"


class TestToolCallRequestModelField:
    """Tests for model field on ToolCallRequest."""

    def test_model_field_default_is_none(self):
        """ToolCallRequest.model defaults to None for backward compatibility."""
        event = ToolCallRequest(
            tool_call_id="call-123",
            tool_name="edit_file",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
        )
        assert event.model is None

    def test_model_field_can_be_set(self):
        """ToolCallRequest.model can be set to a model name."""
        event = ToolCallRequest(
            tool_call_id="call-123",
            tool_name="edit_file",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
            model="claude-sonnet-4-20250514",
        )
        assert event.model == "claude-sonnet-4-20250514"

    def test_model_field_serialized(self):
        """ToolCallRequest.model is included in serialized output."""
        event = ToolCallRequest(
            tool_call_id="call-123",
            tool_name="edit_file",
            timestamp=datetime.datetime(2024, 1, 1, 0, 0, 0),
            model="claude-sonnet-4-20250514",
        )
        data = event.model_dump(mode="json")
        assert data["model"] == "claude-sonnet-4-20250514"
