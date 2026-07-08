"""Tests for context management tools (refocus and branch conversation)."""

from unittest.mock import Mock, patch

import pytest

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.agents.tools.context_management_tools import (
    create_branch_conversation_tool,
    create_refocus_conversation_tool,
)
from devboard.db.models import Conversation, ParentEntityType
from devboard.db.repositories import ConversationRepository
from devboard.services.conversation_service import ConversationService

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_conversation():
    conv = Mock(spec=Conversation)
    conv.id = 10
    conv.parent_entity_type = ParentEntityType.PROJECT
    conv.parent_entity_id = 1
    conv.agent_role = AgentRoleType.PROJECT
    conv.engine = AgentEngine.INTERNAL
    conv.model_id = "anthropic:claude-sonnet-4.5"
    return conv


@pytest.fixture
def mock_new_conversation():
    conv = Mock(spec=Conversation)
    conv.id = 99
    return conv


@pytest.fixture
def mock_conversation_service(mock_new_conversation):
    service = Mock(spec=ConversationService)
    service.create_seeded_conversation.return_value = mock_new_conversation
    return service


@pytest.fixture
def mock_conversation_repo():
    repo = Mock(spec=ConversationRepository)
    repo.db = Mock()
    return repo


class TestRefocusConversationTool:
    """Tests for the refocus_conversation tool."""

    @pytest.mark.asyncio
    async def test_creates_new_conversation_from_source(
        self, mock_conversation, mock_conversation_service, mock_conversation_repo, mock_new_conversation
    ):
        tool = create_refocus_conversation_tool(mock_conversation, mock_conversation_service, mock_conversation_repo)

        with patch("devboard.agents.tools.context_management_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            await tool.function(
                context_summary="Important context here",
                title="Refocused Conversation",
                continuation_prompt="Continue working on the spec",
            )

        mock_conversation_service.create_seeded_conversation.assert_called_once_with(
            mock_conversation, "Refocused Conversation"
        )

    @pytest.mark.asyncio
    async def test_archives_old_conversation(
        self, mock_conversation, mock_conversation_service, mock_conversation_repo
    ):
        tool = create_refocus_conversation_tool(mock_conversation, mock_conversation_service, mock_conversation_repo)

        with patch("devboard.agents.tools.context_management_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            await tool.function(
                context_summary="Context",
                title="New Title",
                continuation_prompt="Continue",
            )

        mock_conversation_repo.archive_conversation.assert_called_once_with(mock_conversation.id)

    @pytest.mark.asyncio
    async def test_starts_agent_execution_in_new_conversation(
        self, mock_conversation, mock_conversation_service, mock_conversation_repo, mock_new_conversation
    ):
        tool = create_refocus_conversation_tool(mock_conversation, mock_conversation_service, mock_conversation_repo)
        mock_execution_manager = Mock()

        with patch(
            "devboard.agents.tools.context_management_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            await tool.function(
                context_summary="My summary",
                title="Title",
                continuation_prompt="Keep going",
            )

        mock_execution_manager.start_agent_execution.assert_called_once()
        call_args = mock_execution_manager.start_agent_execution.call_args
        assert call_args[0][0] == mock_new_conversation.id
        seeded_message = call_args[0][1]
        assert "My summary" in seeded_message
        assert "Keep going" in seeded_message
        assert "continuation_context" in seeded_message

    @pytest.mark.asyncio
    async def test_returns_structured_refocused_string(
        self, mock_conversation, mock_conversation_service, mock_conversation_repo, mock_new_conversation
    ):
        tool = create_refocus_conversation_tool(mock_conversation, mock_conversation_service, mock_conversation_repo)

        with patch("devboard.agents.tools.context_management_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            result = await tool.function(
                context_summary="Context",
                title="Title",
                continuation_prompt="Continue",
            )

        assert result == f"REFOCUSED conversation_id={mock_new_conversation.id}"

    @pytest.mark.asyncio
    async def test_flushes_db_after_archiving(
        self, mock_conversation, mock_conversation_service, mock_conversation_repo
    ):
        tool = create_refocus_conversation_tool(mock_conversation, mock_conversation_service, mock_conversation_repo)

        with patch("devboard.agents.tools.context_management_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            await tool.function(
                context_summary="Context",
                title="Title",
                continuation_prompt="Continue",
            )

        mock_conversation_repo.db.flush.assert_called_once()


class TestBranchConversationTool:
    """Tests for the branch_conversation tool."""

    @pytest.mark.asyncio
    async def test_creates_new_conversation_from_source(
        self, mock_conversation, mock_conversation_service, mock_new_conversation
    ):
        tool = create_branch_conversation_tool(mock_conversation, mock_conversation_service)

        with patch("devboard.agents.tools.context_management_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            await tool.function(
                context_summary="Branch context",
                title="Branch Investigation",
                prompt="Investigate this topic",
            )

        mock_conversation_service.create_seeded_conversation.assert_called_once_with(
            mock_conversation, "Branch Investigation"
        )

    @pytest.mark.asyncio
    async def test_does_not_archive_parent_conversation(
        self, mock_conversation, mock_conversation_service, mock_conversation_repo
    ):
        """Branch must NOT archive the parent conversation."""
        tool = create_branch_conversation_tool(mock_conversation, mock_conversation_service)

        with patch("devboard.agents.tools.context_management_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            await tool.function(
                context_summary="Context",
                title="Title",
                prompt="Investigate",
            )

        # No archiving should happen for branch
        mock_conversation_repo.archive_conversation.assert_not_called()

    @pytest.mark.asyncio
    async def test_starts_agent_execution_in_new_conversation(
        self, mock_conversation, mock_conversation_service, mock_new_conversation
    ):
        tool = create_branch_conversation_tool(mock_conversation, mock_conversation_service)
        mock_execution_manager = Mock()

        with patch(
            "devboard.agents.tools.context_management_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            await tool.function(
                context_summary="Investigation context",
                title="Branch",
                prompt="Look into this",
            )

        mock_execution_manager.start_agent_execution.assert_called_once()
        call_args = mock_execution_manager.start_agent_execution.call_args
        assert call_args[0][0] == mock_new_conversation.id
        seeded_message = call_args[0][1]
        assert "Investigation context" in seeded_message
        assert "Look into this" in seeded_message

    @pytest.mark.asyncio
    async def test_returns_message_with_conversation_id(
        self, mock_conversation, mock_conversation_service, mock_new_conversation
    ):
        tool = create_branch_conversation_tool(mock_conversation, mock_conversation_service)

        with patch("devboard.agents.tools.context_management_tools.get_execution_manager") as mock_get_mgr:
            mock_get_mgr.return_value = Mock()
            result = await tool.function(
                context_summary="Context",
                title="My Branch",
                prompt="Investigate",
            )

        assert str(mock_new_conversation.id) in result
        assert "My Branch" in result
        assert "inspect_conversation" in result
