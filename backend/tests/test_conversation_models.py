"""Tests for conversation models and PydanticAI message serialization."""

import datetime

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from sqlalchemy.orm import Session

from devboard.db.models import (
    ProjectConversationMessage,
    TaskConversationMessage,
)
from devboard.db.models.messages import MessageType, _get_message_type
from devboard.db.repositories import ProjectRepository, TaskRepository


class TestBaseConversationMessage:
    """Test BaseConversationMessage functionality."""

    def test_message_type_detection_user_prompt(self):
        """Test MessageType detection for user prompts."""
        # Create PydanticAI user request message
        message = ModelRequest(parts=[UserPromptPart(content="Hello")])

        # Test the detection logic
        detected_type = _get_message_type(message)
        assert detected_type == MessageType.USER_PROMPT

    def test_message_type_detection_text_response(self):
        """Test MessageType detection for text responses."""
        from pydantic_ai.messages import ModelResponse

        message = ModelResponse(parts=[TextPart(content="Hello back")])

        detected_type = _get_message_type(message)
        assert detected_type == MessageType.TEXT_RESPONSE

    def test_message_type_detection_tool_call(self):
        """Test MessageType detection for tool calls."""
        from pydantic_ai.messages import ModelResponse

        message = ModelResponse(parts=[ToolCallPart(tool_name="edit_document", tool_call_id="123", args={})])

        detected_type = _get_message_type(message)
        assert detected_type == MessageType.TOOL_CALL

    def test_message_type_detection_tool_result(self):
        """Test MessageType detection for tool results."""

        message = ModelRequest(
            parts=[ToolReturnPart(tool_name="test_tool", tool_call_id="123", content="Tool executed successfully")]
        )

        detected_type = _get_message_type(message)
        assert detected_type == MessageType.TOOL_RESULT

    def test_message_type_detection_structured_response(self):
        """Test MessageType detection for structured responses."""
        from pydantic_ai.messages import ModelResponse

        # Create a message with final_result tool call to trigger structured response
        message = ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    tool_call_id="123",
                    args={"data": "structured response"},
                )
            ]
        )

        detected_type = _get_message_type(message)
        assert detected_type == MessageType.STRUCTURED_RESPONSE

    def test_message_type_detection_unknown(self):
        """Test MessageType detection for unknown message types."""
        from pydantic_ai.messages import ModelResponse

        # Create a response with a tool call that's not final_result
        message = ModelResponse(parts=[ToolCallPart(tool_name="unknown_tool", tool_call_id="123", args={})])

        # Should default to TOOL_CALL for unknown response types
        detected_type = _get_message_type(message)
        assert detected_type == MessageType.TOOL_CALL


class TestProjectConversationMessage:
    """Test ProjectConversationMessage model with PydanticAI integration."""

    def test_project_conversation_message_creation(self, db_session: Session):
        """Test creating a ProjectConversationMessage from PydanticAI message."""
        # Create a project first
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        # Create PydanticAI-style message data
        pydantic_message = ModelRequest(parts=[UserPromptPart(content="What is the current status of this project?")])

        # Use the factory method to create message
        message = ProjectConversationMessage.from_pydantic_message(
            entity_id=created_project.id, message=pydantic_message
        )

        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify the message was created correctly
        assert message.id is not None
        assert message.parent_id == created_project.id
        assert message.message_type == MessageType.USER_PROMPT
        assert message.pydantic_content is not None
        assert isinstance(message.timestamp, datetime.datetime)

    def test_project_conversation_message_from_response(self, db_session: Session):
        """Test ProjectConversationMessage from agent response."""
        # Create a project
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        # Create agent response message
        pydantic_message = ModelResponse(parts=[TextPart(content="The project is currently active and on track.")])

        message = ProjectConversationMessage.from_pydantic_message(
            entity_id=created_project.id, message=pydantic_message
        )

        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify response message
        assert message.message_type == MessageType.TEXT_RESPONSE
        assert message.pydantic_content is not None
        assert message.parent_id == created_project.id

    def test_project_message_relationship(self, db_session: Session):
        """Test the relationship between Project and ProjectConversationMessage."""
        # Create project
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        # Create multiple messages
        messages = [
            ModelRequest(parts=[UserPromptPart(content="First message")]),
            ModelResponse(parts=[TextPart(content="First response")]),
            ModelRequest(parts=[UserPromptPart(content="Second message")]),
        ]

        for pydantic_msg in messages:
            message = ProjectConversationMessage.from_pydantic_message(
                entity_id=created_project.id, message=pydantic_msg
            )
            db_session.add(message)

        db_session.commit()
        db_session.refresh(created_project)

        # Test relationship
        assert len(created_project.messages) == 3
        assert all(msg.parent_id == created_project.id for msg in created_project.messages)

        # Test back reference
        first_message = created_project.messages[0]
        assert first_message.project.id == created_project.id


class TestTaskConversationMessage:
    """Test TaskConversationMessage model with PydanticAI integration."""

    def test_task_conversation_message_creation(self, db_session: Session):
        """Test creating a TaskConversationMessage from PydanticAI message."""
        # Create project and task
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(project_id=created_project.id, title="Test Task", status="defining")
        db_session.commit()

        # Create PydanticAI user message
        pydantic_message = ModelRequest(
            parts=[UserPromptPart(content="Please help me design this task specification.")]
        )

        message = TaskConversationMessage.from_pydantic_message(entity_id=created_task.id, message=pydantic_message)

        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify message creation
        assert message.id is not None
        assert message.parent_id == created_task.id
        assert message.message_type == MessageType.USER_PROMPT
        assert message.pydantic_content is not None
        assert isinstance(message.timestamp, datetime.datetime)

    def test_task_conversation_message_relationship(self, db_session: Session):
        """Test the relationship between Task and TaskConversationMessage."""
        # Create task
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(project_id=created_project.id, title="Test Task", status="defining")
        db_session.commit()

        # Create conversation messages
        conversation = [
            ModelRequest(parts=[UserPromptPart(content="Start designing this task")]),
            ModelResponse(parts=[TextPart(content="I'll help you create a task specification")]),
            ModelRequest(parts=[UserPromptPart(content="Can you add more detail?")]),
        ]

        for pydantic_msg in conversation:
            message = TaskConversationMessage.from_pydantic_message(entity_id=created_task.id, message=pydantic_msg)
            db_session.add(message)

        db_session.commit()
        db_session.refresh(created_task)

        # Test relationship
        assert len(created_task.messages) == 3
        assert all(msg.parent_id == created_task.id for msg in created_task.messages)

        # Test back reference
        first_message = created_task.messages[0]
        assert first_message.task.id == created_task.id

    def test_conversation_message_serialization(self, db_session: Session):
        """Test that PydanticAI messages are properly serialized and deserialized."""
        # Create task
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(project_id=created_project.id, title="Test Task", status="planning")
        db_session.commit()

        # Create a complex message with multiple parts
        original_message = ModelResponse(
            parts=[
                TextPart(content="I'll help you with the task planning."),
                # In a real scenario, tool calls would be added here
            ]
        )

        # Store the message
        message = TaskConversationMessage.from_pydantic_message(entity_id=created_task.id, message=original_message)
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify the message content was stored correctly
        assert message.pydantic_content is not None
        assert isinstance(message.pydantic_content, dict)
        assert "parts" in message.pydantic_content

        # The content should be serializable JSON
        parts = message.pydantic_content["parts"]
        assert len(parts) >= 1
        assert parts[0]["part_kind"] == "text"  # PydanticAI uses 'part_kind' not 'kind'
        assert parts[0]["content"] == "I'll help you with the task planning."

    def test_message_timestamps_ordering(self, db_session: Session):
        """Test that timestamps are properly set and ordered."""
        # Create task
        project_repo = ProjectRepository(db_session)
        created_project = project_repo.create(name="Test Project", description="A test project for development")
        db_session.commit()

        task_repo = TaskRepository(db_session)
        created_task = task_repo.create(project_id=created_project.id, title="Test Task", status="defining")
        db_session.commit()

        # Create messages with slight delay
        import time

        message1 = TaskConversationMessage.from_pydantic_message(
            entity_id=created_task.id,
            message=ModelRequest(parts=[UserPromptPart(content="First message")]),
        )
        db_session.add(message1)
        db_session.commit()

        time.sleep(0.01)  # Small delay

        message2 = TaskConversationMessage.from_pydantic_message(
            entity_id=created_task.id,
            message=ModelResponse(parts=[TextPart(content="Second message")]),
        )
        db_session.add(message2)
        db_session.commit()

        db_session.refresh(message1)
        db_session.refresh(message2)

        # Verify timestamps
        assert message1.timestamp < message2.timestamp
        assert isinstance(message1.timestamp, datetime.datetime)
        assert isinstance(message2.timestamp, datetime.datetime)

    def test_from_pydantic_message_factory_method(self):
        """Test the factory method works correctly."""
        # Test with user request
        user_message = ModelRequest(parts=[UserPromptPart(content="Test user message")])

        task_msg = TaskConversationMessage.from_pydantic_message(entity_id=123, message=user_message)

        assert task_msg.parent_id == 123
        assert task_msg.message_type == MessageType.USER_PROMPT
        assert task_msg.pydantic_content is not None

        # Test with agent response
        agent_message = ModelResponse(parts=[TextPart(content="Test agent response")])

        project_msg = ProjectConversationMessage.from_pydantic_message(entity_id=456, message=agent_message)

        assert project_msg.parent_id == 456
        assert project_msg.message_type == MessageType.TEXT_RESPONSE
        assert project_msg.pydantic_content is not None
