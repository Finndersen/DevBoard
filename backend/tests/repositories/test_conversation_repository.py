import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Conversation, ParentEntityType, Project
from devboard.db.repositories import ConversationRepository


class TestConversationRepository:
    """Tests for ConversationRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ConversationRepository:
        return ConversationRepository(db_session)

    @pytest.fixture
    def project(self, db_session: Session) -> Project:
        """Create a test project for conversation relationships."""
        from devboard.db.repositories.project import ProjectRepository

        project_repo = ProjectRepository(db_session)
        project = project_repo.create(name="Test Project", description="")
        db_session.flush()
        return project

    @pytest.fixture
    def conversation(self, repo: ConversationRepository, project: Project) -> Conversation:
        """Create a test conversation."""
        conversation = repo.get_or_create_for_entity(ParentEntityType.PROJECT, project.id)
        return conversation

    def test_get_or_create_for_entity_creates_new(
        self,
        repo: ConversationRepository,
        project: Project,
        db_session,
    ):
        """Test creating a new conversation for entity."""
        conversation = repo.get_or_create_for_entity(ParentEntityType.PROJECT, project.id)
        db_session.commit()

        assert conversation.id is not None
        assert conversation.parent_entity_type == ParentEntityType.PROJECT
        assert conversation.parent_entity_id == project.id
        assert conversation.parent_conversation_id is None

    def test_get_or_create_for_entity_returns_existing(
        self,
        repo: ConversationRepository,
        project: Project,
        db_session,
    ):
        """Test getting existing conversation for entity."""
        # Create first conversation
        conversation1 = repo.get_or_create_for_entity("project", project.id)
        db_session.commit()

        # Get same conversation
        conversation2 = repo.get_or_create_for_entity("project", project.id)

        assert conversation1.id == conversation2.id

    def test_get_by_id(
        self,
        repo: ConversationRepository,
        conversation: Conversation,
        db_session,
    ):
        """Test getting a conversation by ID."""
        db_session.commit()
        retrieved = repo.get_by_id(conversation.id)

        assert retrieved is not None
        assert retrieved.id == conversation.id
        assert retrieved.parent_entity_type == conversation.parent_entity_type

    def test_get_by_id_not_found(self, repo: ConversationRepository):
        """Test getting a conversation by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_create_message(
        self,
        repo: ConversationRepository,
        conversation: Conversation,
        db_session,
    ):
        """Test creating a new message."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        pydantic_message = ModelRequest(parts=[UserPromptPart(content="Test message")])
        created = repo.create_message(conversation.id, pydantic_message)
        db_session.commit()

        assert created.id is not None
        assert created.text_content == "Test message"
        assert created.conversation_id == conversation.id

    def test_get_messages(
        self,
        repo: ConversationRepository,
        conversation: Conversation,
        db_session,
    ):
        """Test getting all messages for a conversation."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        # Create messages
        message1 = ModelRequest(parts=[UserPromptPart(content="First message")])
        message2 = ModelResponse(parts=[TextPart(content="Second message")])

        repo.create_message(conversation.id, message2)
        repo.create_message(conversation.id, message1)
        db_session.commit()

        messages = repo.get_messages(conversation.id)
        assert len(messages) == 2
        # Should be ordered by timestamp ascending
        assert messages[0].timestamp <= messages[1].timestamp

    def test_get_messages_exclude_tool_calls(
        self,
        repo: ConversationRepository,
        conversation: Conversation,
        db_session,
    ):
        """Test getting messages excluding tool calls."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        # Create user message
        message1 = ModelRequest(parts=[UserPromptPart(content="User message")])
        repo.create_message(conversation.id, message1)

        db_session.commit()

        # Get messages excluding tool calls
        messages = repo.get_messages(conversation.id, exclude_tool_calls=True)
        assert len(messages) == 1
        assert messages[0].text_content == "User message"

    def test_delete_messages(
        self,
        repo: ConversationRepository,
        conversation: Conversation,
        db_session,
    ):
        """Test deleting all messages in a conversation."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        # Create messages
        message1 = ModelRequest(parts=[UserPromptPart(content="Message 1")])
        message2 = ModelRequest(parts=[UserPromptPart(content="Message 2")])

        repo.create_message(conversation.id, message1)
        repo.create_message(conversation.id, message2)
        db_session.commit()

        # Delete messages
        deleted_count = repo.delete_messages(conversation.id)
        db_session.commit()

        assert deleted_count == 2

        # Verify messages are deleted
        messages = repo.get_messages(conversation.id)
        assert len(messages) == 0

    def test_convert_messages_to_pydantic(
        self,
        repo: ConversationRepository,
        conversation: Conversation,
        db_session,
    ):
        """Test converting database messages to pydantic messages."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        # Create message
        pydantic_message = ModelRequest(parts=[UserPromptPart(content="Test message")])
        repo.create_message(conversation.id, pydantic_message)
        db_session.commit()

        # Get messages and convert
        messages = repo.get_messages(conversation.id)
        converted = repo.convert_messages_to_pydantic(messages)

        assert len(converted) == 1
        assert isinstance(converted[0], ModelRequest)
        assert converted[0].parts[0].content == "Test message"
