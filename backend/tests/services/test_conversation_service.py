"""Tests for ConversationService new methods."""

from unittest.mock import Mock

import pytest

from devboard.agents.config_types import AgentEngineModelConfig
from devboard.agents.engines import AgentEngine
from devboard.agents.language_models import LanguageModel, LLMProvider, ModelType
from devboard.db.models import Conversation, ParentEntityType
from devboard.db.repositories import ConversationRepository
from devboard.services.conversation_service import (
    MAX_PROJECT_CONVERSATIONS,
    ConversationService,
    CreateConversationResult,
)


@pytest.fixture
def mock_conversation_repo():
    return Mock(spec=ConversationRepository)


@pytest.fixture
def mock_agent_config_service():
    mock_service = Mock()
    mock_model = LanguageModel(provider=LLMProvider.OPENAI, name="gpt-4", type=ModelType.STANDARD)
    default_config = AgentEngineModelConfig(engine=AgentEngine.INTERNAL, model=mock_model)
    mock_service.get_effective_config.return_value = default_config
    return mock_service


@pytest.fixture
def conversation_service(mock_conversation_repo, mock_agent_config_service):
    return ConversationService(
        conversation_repo=mock_conversation_repo,
        agent_config_service=mock_agent_config_service,
    )


class TestCreateProjectConversation:
    """Tests for create_project_conversation method."""

    def test_creates_conversation_under_cap(self, conversation_service, mock_conversation_repo):
        mock_conversation_repo.count_active_for_entity.return_value = 5

        mock_conv = Mock(spec=Conversation)
        mock_conv.id = 1
        mock_conversation_repo.create.return_value = mock_conv

        result = conversation_service.create_project_conversation(project_id=42)

        assert isinstance(result, CreateConversationResult)
        assert result.conversation is mock_conv
        assert result.at_cap is False
        mock_conversation_repo.get_oldest_active_for_entity.assert_not_called()
        mock_conversation_repo.delete_by_id.assert_not_called()

    def test_deletes_oldest_when_at_cap(self, conversation_service, mock_conversation_repo):
        mock_conversation_repo.count_active_for_entity.return_value = MAX_PROJECT_CONVERSATIONS

        oldest_conv = Mock(spec=Conversation)
        oldest_conv.id = 99
        mock_conversation_repo.get_oldest_active_for_entity.return_value = oldest_conv

        new_conv = Mock(spec=Conversation)
        new_conv.id = 100
        mock_conversation_repo.create.return_value = new_conv

        result = conversation_service.create_project_conversation(project_id=42)

        assert result.conversation is new_conv
        assert result.at_cap is True
        mock_conversation_repo.delete_by_id.assert_called_once_with(99)

    def test_at_cap_false_when_one_below(self, conversation_service, mock_conversation_repo):
        mock_conversation_repo.count_active_for_entity.return_value = MAX_PROJECT_CONVERSATIONS - 2

        mock_conv = Mock(spec=Conversation)
        mock_conversation_repo.create.return_value = mock_conv

        result = conversation_service.create_project_conversation(project_id=42)

        assert result.at_cap is False

    def test_at_cap_true_when_exactly_at_cap_minus_one(self, conversation_service, mock_conversation_repo):
        """When count is cap-1, after creating one more it becomes cap, so at_cap=True."""
        mock_conversation_repo.count_active_for_entity.return_value = MAX_PROJECT_CONVERSATIONS - 1

        mock_conv = Mock(spec=Conversation)
        mock_conversation_repo.create.return_value = mock_conv

        result = conversation_service.create_project_conversation(project_id=42)

        assert result.at_cap is True

    def test_calls_repo_with_correct_entity_type(self, conversation_service, mock_conversation_repo):
        mock_conversation_repo.count_active_for_entity.return_value = 0

        mock_conv = Mock(spec=Conversation)
        mock_conversation_repo.create.return_value = mock_conv

        conversation_service.create_project_conversation(project_id=7)

        mock_conversation_repo.count_active_for_entity.assert_called_once_with(ParentEntityType.PROJECT, 7)


class TestSetConversationTitleFromMessage:
    """Tests for set_conversation_title_from_message method."""

    def test_sets_title_when_none(self, conversation_service, mock_conversation_repo):
        conv = Mock(spec=Conversation)
        conv.title = None

        conversation_service.set_conversation_title_from_message(conv, "Hello, help me with this project")

        mock_conversation_repo.update_title.assert_called_once_with(conv, "Hello, help me with this project")

    def test_does_not_set_title_when_already_set(self, conversation_service, mock_conversation_repo):
        conv = Mock(spec=Conversation)
        conv.title = "Existing Title"

        conversation_service.set_conversation_title_from_message(conv, "New message")

        mock_conversation_repo.update_title.assert_not_called()

    def test_truncates_message_to_80_chars(self, conversation_service, mock_conversation_repo):
        conv = Mock(spec=Conversation)
        conv.title = None
        long_message = "A" * 120

        conversation_service.set_conversation_title_from_message(conv, long_message)

        mock_conversation_repo.update_title.assert_called_once_with(conv, "A" * 80)

    def test_does_not_set_empty_title_from_whitespace(self, conversation_service, mock_conversation_repo):
        conv = Mock(spec=Conversation)
        conv.title = None

        conversation_service.set_conversation_title_from_message(conv, "   ")

        mock_conversation_repo.update_title.assert_not_called()

    def test_strips_whitespace_from_message(self, conversation_service, mock_conversation_repo):
        conv = Mock(spec=Conversation)
        conv.title = None

        conversation_service.set_conversation_title_from_message(conv, "  Hello world  ")

        mock_conversation_repo.update_title.assert_called_once_with(conv, "Hello world")
