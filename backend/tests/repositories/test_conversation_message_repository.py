import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Project, ProjectConversationMessage
from devboard.db.repositories import ProjectConversationMessageRepository


class TestProjectConversationMessageRepository:
    """Tests for ProjectConversationMessageRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ProjectConversationMessageRepository:
        return ProjectConversationMessageRepository(db_session)

    @pytest.fixture
    def project(self, db_session: Session) -> Project:
        """Create a test project for message relationships."""
        from devboard.db.repositories.project import ProjectRepository

        project_repo = ProjectRepository(db_session)
        project = project_repo.create(name="Test Project", description="")
        db_session.flush()
        return project

    @pytest.fixture
    def sample_message(self, project: Project) -> ProjectConversationMessage:
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        pydantic_message = ModelRequest(parts=[UserPromptPart(content="Test message")])
        return ProjectConversationMessage.from_pydantic_message(project.id, pydantic_message)

    def test_create_message(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test creating a new message."""
        created = repo.create(sample_message)
        db_session.commit()
        assert created.id is not None
        assert created.text_content == "Test message"

    def test_get_by_id(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test getting a message by ID."""
        created = repo.create(sample_message)
        db_session.commit()
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.text_content == created.text_content

    def test_get_by_id_not_found(self, repo: ProjectConversationMessageRepository):
        """Test getting a message by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all_for_entity(self, repo: ProjectConversationMessageRepository, project: Project, db_session):
        """Test getting all messages for an entity, ordered by timestamp."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        message1 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelRequest(parts=[UserPromptPart(content="First message")])
        )
        message2 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="Second message")])
        )

        # Create in reverse order to test ordering
        repo.create(message2)
        repo.create(message1)
        db_session.commit()

        messages = repo.get_all_for_entity(project.id)
        assert len(messages) == 2
        # Should be ordered by timestamp ascending
        assert messages[0].timestamp <= messages[1].timestamp

    def test_update_message(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test updating a message."""
        from pydantic_ai.messages import ModelResponse, TextPart
        from pydantic_core import to_jsonable_python

        from devboard.db.models.messages import _get_message_type

        created = repo.create(sample_message)
        db_session.commit()

        # Update to a response message
        response_message = ModelResponse(parts=[TextPart(content="Updated message content")])
        created.pydantic_content = to_jsonable_python(response_message)
        created.message_type = _get_message_type(response_message)

        updated = repo.update(created)
        db_session.commit()
        assert updated.text_content == "Updated message content"

    def test_delete_by_id(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test deleting a message by ID."""
        created = repo.create(sample_message)
        db_session.commit()
        result = repo.delete_by_id(created.id)
        db_session.commit()

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ProjectConversationMessageRepository):
        """Test deleting a message by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False

    def test_delete_all_for_entity(self, repo: ProjectConversationMessageRepository, project: Project, db_session):
        """Test deleting all messages for an entity."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        message1 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelRequest(parts=[UserPromptPart(content="Message 1")])
        )
        message2 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="Message 2")])
        )

        repo.create(message1)
        repo.create(message2)
        db_session.commit()

        count = repo.delete_all_for_entity(project.id)
        db_session.commit()
        assert count == 2

        remaining_messages = repo.get_all_for_entity(project.id)
        assert len(remaining_messages) == 0

    def test_delete_tool_approval_messages_with_complete_flow(
        self, repo: ProjectConversationMessageRepository, project: Project, db_session
    ):
        """Test deleting tool approval messages from a complete conversation flow."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            ToolCallPart,
            UserPromptPart,
        )

        # Create a complete conversation flow:
        # 1. Initial user message
        # 2. Agent response
        # 3. User message that triggers tool call
        # 4. Agent tool call
        initial_message = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelRequest(parts=[UserPromptPart(content="Hello")])
        )
        initial_response = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="Hi there")])
        )
        user_request = ProjectConversationMessage.from_pydantic_message(
            project.id,
            ModelRequest(parts=[UserPromptPart(content="Edit this document")]),
        )
        tool_call = ProjectConversationMessage.from_pydantic_message(
            project.id,
            ModelResponse(parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_123", args={})]),
        )

        repo.create(initial_message)
        repo.create(initial_response)
        repo.create(user_request)
        repo.create(tool_call)
        db_session.commit()

        # Verify all messages exist
        all_messages = repo.get_all_for_entity(project.id)
        assert len(all_messages) == 4

        # Delete tool approval messages (should delete from the last user prompt onwards)
        deleted_count = repo.delete_tool_approval_messages(project.id)
        db_session.commit()

        # Should delete the user request and tool call (2 messages)
        assert deleted_count == 2

        # Verify only the initial conversation remains
        remaining_messages = repo.get_all_for_entity(project.id)
        assert len(remaining_messages) == 2
        assert remaining_messages[0].text_content == "Hello"
        assert remaining_messages[1].text_content == "Hi there"

    def test_delete_tool_approval_messages_with_only_tool_call(
        self, repo: ProjectConversationMessageRepository, project: Project, db_session
    ):
        """Test deleting tool approval messages when only tool call exists."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            ToolCallPart,
            UserPromptPart,
        )

        # Create conversation with user message followed by tool call
        user_message = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelRequest(parts=[UserPromptPart(content="Edit this")])
        )
        tool_call = ProjectConversationMessage.from_pydantic_message(
            project.id,
            ModelResponse(parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_456", args={})]),
        )

        repo.create(user_message)
        repo.create(tool_call)
        db_session.commit()

        # Delete tool approval messages
        deleted_count = repo.delete_tool_approval_messages(project.id)
        db_session.commit()

        # Should delete both messages (from last user prompt onwards)
        assert deleted_count == 2

        remaining_messages = repo.get_all_for_entity(project.id)
        assert len(remaining_messages) == 0

    def test_delete_tool_approval_messages_with_no_user_prompt(
        self, repo: ProjectConversationMessageRepository, project: Project, db_session
    ):
        """Test deleting tool approval messages when there's no user prompt."""
        from pydantic_ai.messages import ModelResponse, TextPart

        # Create only agent responses (no user prompts)
        response1 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="Response 1")])
        )
        response2 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="Response 2")])
        )

        repo.create(response1)
        repo.create(response2)
        db_session.commit()

        # Delete tool approval messages - should delete nothing since there's no USER_PROMPT
        deleted_count = repo.delete_tool_approval_messages(project.id)
        db_session.commit()

        assert deleted_count == 0

        remaining_messages = repo.get_all_for_entity(project.id)
        assert len(remaining_messages) == 2

    def test_delete_tool_approval_messages_with_empty_conversation(
        self, repo: ProjectConversationMessageRepository, project: Project, db_session
    ):
        """Test deleting tool approval messages from empty conversation."""
        # No messages exist
        deleted_count = repo.delete_tool_approval_messages(project.id)
        db_session.commit()

        assert deleted_count == 0

        remaining_messages = repo.get_all_for_entity(project.id)
        assert len(remaining_messages) == 0

    def test_delete_tool_approval_messages_with_multiple_user_prompts(
        self, repo: ProjectConversationMessageRepository, project: Project, db_session
    ):
        """Test deleting tool approval messages with multiple user prompts (should delete from last one)."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            ToolCallPart,
            UserPromptPart,
        )

        # Create conversation with multiple user prompts
        user1 = ProjectConversationMessage.from_pydantic_message(
            project.id,
            ModelRequest(parts=[UserPromptPart(content="First user message")]),
        )
        response1 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="First response")])
        )
        user2 = ProjectConversationMessage.from_pydantic_message(
            project.id,
            ModelRequest(parts=[UserPromptPart(content="Second user message")]),
        )
        tool_call = ProjectConversationMessage.from_pydantic_message(
            project.id,
            ModelResponse(parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_789", args={})]),
        )

        repo.create(user1)
        repo.create(response1)
        repo.create(user2)
        repo.create(tool_call)
        db_session.commit()

        # Delete tool approval messages (should delete from the LAST user prompt onwards)
        deleted_count = repo.delete_tool_approval_messages(project.id)
        db_session.commit()

        # Should delete user2 and tool_call (2 messages)
        assert deleted_count == 2

        # Verify first conversation pair remains
        remaining_messages = repo.get_all_for_entity(project.id)
        assert len(remaining_messages) == 2
        assert remaining_messages[0].text_content == "First user message"
        assert remaining_messages[1].text_content == "First response"


class TestTaskConversationMessageRepository:
    """Tests for TaskConversationMessageRepository including delete_tool_approval_messages."""

    @pytest.fixture
    def repo(self, db_session: Session):
        from devboard.db.repositories.conversation_message import (
            TaskConversationMessageRepository,
        )

        return TaskConversationMessageRepository(db_session)

    @pytest.fixture
    def task(self, db_session: Session):
        """Create a test task for message relationships."""
        from devboard.db.repositories.project import ProjectRepository
        from devboard.db.repositories.task import TaskRepository

        # Create project first
        project_repo = ProjectRepository(db_session)
        project = project_repo.create(name="Test Project", description="")
        db_session.flush()

        # Create task
        task_repo = TaskRepository(db_session)
        task = task_repo.create(project_id=project.id, title="Test Task")
        db_session.flush()
        return task

    def test_delete_tool_approval_messages_with_complete_flow(self, repo, task, db_session):
        """Test deleting tool approval messages from a complete task conversation flow."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            ToolCallPart,
            UserPromptPart,
        )

        from devboard.db.models import TaskConversationMessage

        # Create a complete conversation flow
        initial_message = TaskConversationMessage.from_pydantic_message(
            task.id, ModelRequest(parts=[UserPromptPart(content="Hello")])
        )
        initial_response = TaskConversationMessage.from_pydantic_message(
            task.id, ModelResponse(parts=[TextPart(content="Hi there")])
        )
        user_request = TaskConversationMessage.from_pydantic_message(
            task.id,
            ModelRequest(parts=[UserPromptPart(content="Edit the specification")]),
        )
        tool_call = TaskConversationMessage.from_pydantic_message(
            task.id,
            ModelResponse(parts=[ToolCallPart(tool_name="edit_document", tool_call_id="tool_123", args={})]),
        )

        repo.create(initial_message)
        repo.create(initial_response)
        repo.create(user_request)
        repo.create(tool_call)
        db_session.commit()

        # Verify all messages exist
        all_messages = repo.get_all_for_entity(task.id)
        assert len(all_messages) == 4

        # Delete tool approval messages (should delete from the last user prompt onwards)
        deleted_count = repo.delete_tool_approval_messages(task.id)
        db_session.commit()

        # Should delete the user request and tool call (2 messages)
        assert deleted_count == 2

        # Verify only the initial conversation remains
        remaining_messages = repo.get_all_for_entity(task.id)
        assert len(remaining_messages) == 2
        assert remaining_messages[0].text_content == "Hello"
        assert remaining_messages[1].text_content == "Hi there"

    def test_delete_tool_approval_messages_with_empty_conversation(self, repo, task, db_session):
        """Test deleting tool approval messages from empty task conversation."""
        # No messages exist
        deleted_count = repo.delete_tool_approval_messages(task.id)
        db_session.commit()

        assert deleted_count == 0

        remaining_messages = repo.get_all_for_entity(task.id)
        assert len(remaining_messages) == 0
