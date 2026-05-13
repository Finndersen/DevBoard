"""Tests for conversation and agent config tools."""

import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from pydantic_ai import ModelRetry, Tool

from devboard.agents.conversation_history import ConversationHistory
from devboard.agents.engines import AgentEngine
from devboard.agents.events import (
    LocalCommand,
    LocalCommandType,
    MessageRole,
    MetaMessage,
    MetaMessageType,
    SystemEvent,
    SystemEventType,
    TextMessage,
    ThinkingEvent,
    ToolCall,
    ToolCallRequest,
    ToolResult,
)
from devboard.agents.roles import AgentRoleType
from devboard.agents.tools.conversation_tools import (
    _format_events,
    _format_tool_args,
    _truncate,
    create_inspect_conversation_tool,
    create_list_conversations_tool,
    create_view_agent_config_tool,
    create_view_conversation_content_tool,
    create_view_conversation_details_tool,
)
from devboard.api.schemas.agent_config import AgentConfigResponse, ToolInfo
from devboard.db.models import ParentEntityType
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.db.repositories.conversation import ConversationListRow

UTC = datetime.UTC
FIXED_TS = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)


@pytest.fixture
def mock_conversation():
    """Create a mock Conversation with typical fields."""
    conv = Mock()
    conv.id = 42
    conv.title = "Test Conversation"
    conv.parent_entity_type = ParentEntityType.TASK
    conv.parent_entity_id = 7
    conv.parent_conversation_id = None
    conv.agent_role = AgentRoleType.TASK_PLANNING
    conv.engine = AgentEngine.INTERNAL
    conv.model_id = "anthropic:claude-sonnet-4"
    conv.is_active = True
    conv.created_at = FIXED_TS
    conv.last_activity_at = FIXED_TS
    return conv


@pytest.fixture
def mock_conversation_repo():
    """Create a mock ConversationRepository."""
    return Mock(spec=ConversationRepository)


@pytest.fixture
def mock_execution_manager():
    """Create a mock ConversationExecutionManager."""
    manager = Mock()
    manager.has_active_execution.return_value = False
    return manager


@pytest.fixture
def conversation_list_row(mock_conversation) -> ConversationListRow:
    """Create a ConversationListRow dict for testing list_conversations."""
    return ConversationListRow(
        conversation=mock_conversation,
        parent_entity_name="My Task",
        project_name="My Project",
    )


# ──────────────────────────────────────────────
# Helper function tests
# ──────────────────────────────────────────────


class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", 10) == "hello"

    def test_long_string_truncated(self):
        result = _truncate("a" * 600)
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        assert _truncate("a" * 500) == "a" * 500


class TestFormatToolArgs:
    def test_none_args_returns_empty(self):
        assert _format_tool_args(None) == ""

    def test_empty_dict_returns_empty(self):
        assert _format_tool_args({}) == ""

    def test_string_value(self):
        result = _format_tool_args({"key": "value"})
        assert result == "key=value"

    def test_non_string_value_json_encoded(self):
        result = _format_tool_args({"count": 5})
        assert result == "count=5"

    def test_multiple_args(self):
        result = _format_tool_args({"a": "x", "b": "y"})
        assert result == "a=x, b=y"

    def test_long_value_truncated(self):
        result = _format_tool_args({"key": "a" * 300})
        assert len(result) < 300
        assert "..." in result


class TestFormatEvents:
    def _ts(self) -> datetime.datetime:
        return FIXED_TS

    def test_text_message_user(self):
        event = TextMessage(role=MessageRole.USER, text_content="Hello!", timestamp=self._ts())
        result = _format_events([event], include_thinking=False)
        assert "USER: Hello!" in result

    def test_text_message_agent(self):
        event = TextMessage(role=MessageRole.AGENT, text_content="World!", timestamp=self._ts())
        result = _format_events([event], include_thinking=False)
        assert "AGENT: World!" in result

    def test_tool_call_with_args(self):
        event = ToolCall(
            tool_call_id="tc1",
            tool_name="list_tasks",
            tool_args={"status": "planning"},
            timestamp=self._ts(),
        )
        result = _format_events([event], include_thinking=False)
        assert "TOOL_CALL list_tasks" in result
        assert "status=planning" in result

    def test_tool_call_no_args(self):
        event = ToolCall(tool_call_id="tc1", tool_name="get_info", tool_args=None, timestamp=self._ts())
        result = _format_events([event], include_thinking=False)
        assert "TOOL_CALL get_info" in result

    def test_tool_result(self):
        event = ToolResult(tool_call_id="tc1", result_content="task data here", timestamp=self._ts())
        result = _format_events([event], include_thinking=False)
        assert "→ RESULT: task data here" in result

    def test_system_event(self):
        event = SystemEvent(
            sub_type=SystemEventType.TASK_UPDATED,
            data={"task_id": 1},
            timestamp=self._ts(),
        )
        result = _format_events([event], include_thinking=False)
        assert "SYSTEM [task_updated]" in result

    def test_thinking_event_excluded_by_default(self):
        event = ThinkingEvent(thinking_text="deep thoughts", timestamp=self._ts())
        result = _format_events([event], include_thinking=False)
        assert "THINKING" not in result

    def test_thinking_event_included_when_requested(self):
        event = ThinkingEvent(thinking_text="deep thoughts", timestamp=self._ts())
        result = _format_events([event], include_thinking=True)
        assert "THINKING: deep thoughts" in result

    def test_thinking_event_with_no_text_skipped(self):
        event = ThinkingEvent(thinking_text=None, timestamp=self._ts())
        result = _format_events([event], include_thinking=True)
        assert "THINKING" not in result

    def test_meta_message(self):
        event = MetaMessage(
            meta_type=MetaMessageType.COMPACT_SUMMARY,
            text_content="Summary here",
            timestamp=self._ts(),
        )
        result = _format_events([event], include_thinking=False)
        assert "META [compact_summary]: Summary here" in result

    def test_local_command(self):
        event = LocalCommand(
            command_type=LocalCommandType.SHELL,
            command="ls -la",
            output="file1.py",
            timestamp=self._ts(),
        )
        result = _format_events([event], include_thinking=False)
        assert "CMD [shell]: ls -la" in result
        assert "→ file1.py" in result

    def test_tool_call_request_skipped(self):
        event = ToolCallRequest(tool_call_id="tc1", tool_name="run_bash", timestamp=self._ts())
        result = _format_events([event], include_thinking=False)
        assert result == "No conversation content found."

    def test_empty_events(self):
        result = _format_events([], include_thinking=False)
        assert result == "No conversation content found."

    def test_long_text_truncated(self):
        long_text = "x" * 600
        event = TextMessage(role=MessageRole.USER, text_content=long_text, timestamp=self._ts())
        result = _format_events([event], include_thinking=False)
        assert "..." in result
        assert "x" * 600 not in result


# ──────────────────────────────────────────────
# create_list_conversations_tool tests
# ──────────────────────────────────────────────


class TestCreateListConversationsTool:
    def test_tool_creation(self, mock_conversation_repo):
        tool = create_list_conversations_tool(mock_conversation_repo)
        assert isinstance(tool, Tool)
        assert tool.name == "list_conversations"

    @pytest.mark.asyncio
    async def test_no_filters_returns_all_conversations(
        self, mock_conversation_repo, mock_execution_manager, conversation_list_row
    ):
        mock_conversation_repo.get_all_top_level.return_value = [conversation_list_row]

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_list_conversations_tool(mock_conversation_repo)
            result = await tool.function()

        mock_conversation_repo.get_all_top_level.assert_called_once_with(
            parent_entity_type=None,
            parent_entity_id=None,
            agent_role=None,
        )
        assert "[42]" in result
        assert "task_planning" in result
        assert "My Task" in result
        assert "My Project" in result

    @pytest.mark.asyncio
    async def test_filter_by_parent_entity_type(
        self, mock_conversation_repo, mock_execution_manager, conversation_list_row
    ):
        mock_conversation_repo.get_all_top_level.return_value = [conversation_list_row]

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_list_conversations_tool(mock_conversation_repo)
            await tool.function(parent_entity_type="task")

        mock_conversation_repo.get_all_top_level.assert_called_once_with(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=None,
            agent_role=None,
        )

    @pytest.mark.asyncio
    async def test_filter_by_agent_role(self, mock_conversation_repo, mock_execution_manager, conversation_list_row):
        mock_conversation_repo.get_all_top_level.return_value = [conversation_list_row]

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_list_conversations_tool(mock_conversation_repo)
            await tool.function(agent_role="task_planning")

        mock_conversation_repo.get_all_top_level.assert_called_once_with(
            parent_entity_type=None,
            parent_entity_id=None,
            agent_role=AgentRoleType.TASK_PLANNING,
        )

    @pytest.mark.asyncio
    async def test_filter_by_is_running_true(
        self, mock_conversation_repo, mock_execution_manager, conversation_list_row
    ):
        mock_conversation_repo.get_all_top_level.return_value = [conversation_list_row]
        mock_execution_manager.has_active_execution.return_value = False  # not running

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_list_conversations_tool(mock_conversation_repo)
            result = await tool.function(is_running=True)

        # Conversation is not running, so it should be filtered out
        assert "No conversations found" in result

    @pytest.mark.asyncio
    async def test_filter_by_is_running_false(
        self, mock_conversation_repo, mock_execution_manager, conversation_list_row
    ):
        mock_conversation_repo.get_all_top_level.return_value = [conversation_list_row]
        mock_execution_manager.has_active_execution.return_value = False

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_list_conversations_tool(mock_conversation_repo)
            result = await tool.function(is_running=False)

        assert "[42]" in result

    @pytest.mark.asyncio
    async def test_is_running_shown_in_output(
        self, mock_conversation_repo, mock_execution_manager, conversation_list_row
    ):
        mock_conversation_repo.get_all_top_level.return_value = [conversation_list_row]
        mock_execution_manager.has_active_execution.return_value = True

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_list_conversations_tool(mock_conversation_repo)
            result = await tool.function()

        assert "running: yes" in result

    @pytest.mark.asyncio
    async def test_invalid_parent_entity_type_raises_model_retry(self, mock_conversation_repo):
        tool = create_list_conversations_tool(mock_conversation_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(parent_entity_type="invalid_type")

        assert "Invalid parent_entity_type" in str(exc_info.value)
        assert "Valid values:" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_agent_role_raises_model_retry(self, mock_conversation_repo):
        tool = create_list_conversations_tool(mock_conversation_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(agent_role="not_a_role")

        assert "Invalid agent_role" in str(exc_info.value)
        assert "Valid values:" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_conversation_repo, mock_execution_manager):
        mock_conversation_repo.get_all_top_level.return_value = []

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_list_conversations_tool(mock_conversation_repo)
            result = await tool.function()

        assert "No conversations found" in result


# ──────────────────────────────────────────────
# create_view_conversation_details_tool tests
# ──────────────────────────────────────────────


class TestCreateViewConversationDetailsTool:
    def test_tool_creation(self, mock_conversation_repo):
        tool = create_view_conversation_details_tool(mock_conversation_repo)
        assert isinstance(tool, Tool)
        assert tool.name == "view_conversation_details"

    @pytest.mark.asyncio
    async def test_returns_metadata_for_found_conversation(
        self, mock_conversation_repo, mock_conversation, mock_execution_manager
    ):
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_view_conversation_details_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42)

        assert "ID: 42" in result
        assert "Title: Test Conversation" in result
        assert "Agent Role: task_planning" in result
        assert "Engine: internal" in result
        assert "Model: anthropic:claude-sonnet-4" in result
        assert "Is Active: yes" in result
        assert "Is Running: no" in result
        assert "Parent Conversation ID: (none)" in result

    @pytest.mark.asyncio
    async def test_not_found_raises_model_retry(self, mock_conversation_repo):
        mock_conversation_repo.get_by_id.return_value = None

        tool = create_view_conversation_details_tool(mock_conversation_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(conversation_id=99)

        assert "99" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_is_running_shown_when_active(
        self, mock_conversation_repo, mock_conversation, mock_execution_manager
    ):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        mock_execution_manager.has_active_execution.return_value = True

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_view_conversation_details_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42)

        assert "Is Running: yes" in result

    @pytest.mark.asyncio
    async def test_default_model_shown_when_none(
        self, mock_conversation_repo, mock_conversation, mock_execution_manager
    ):
        mock_conversation.model_id = None
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        with patch(
            "devboard.agents.tools.conversation_tools.get_execution_manager",
            return_value=mock_execution_manager,
        ):
            tool = create_view_conversation_details_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42)

        assert "Model: default" in result


# ──────────────────────────────────────────────
# create_view_conversation_content_tool tests
# ──────────────────────────────────────────────


class TestCreateViewConversationContentTool:
    def test_tool_creation(self, mock_conversation_repo):
        tool = create_view_conversation_content_tool(mock_conversation_repo)
        assert isinstance(tool, Tool)
        assert tool.name == "view_conversation_content"

    @pytest.mark.asyncio
    async def test_not_found_raises_model_retry(self, mock_conversation_repo):
        mock_conversation_repo.get_by_id.return_value = None

        tool = create_view_conversation_content_tool(mock_conversation_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(conversation_id=99)

        assert "99" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_formats_text_messages(self, mock_conversation_repo, mock_conversation):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        events = [
            TextMessage(role=MessageRole.USER, text_content="Hello agent!", timestamp=FIXED_TS),
            TextMessage(role=MessageRole.AGENT, text_content="Hello user!", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        with patch(
            "devboard.agents.tools.conversation_tools.create_conversation_history_service",
            return_value=mock_history_service,
        ):
            tool = create_view_conversation_content_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42)

        assert "USER: Hello agent!" in result
        assert "AGENT: Hello user!" in result

    @pytest.mark.asyncio
    async def test_include_thinking_false_omits_thinking(self, mock_conversation_repo, mock_conversation):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        events = [
            ThinkingEvent(thinking_text="secret thoughts", timestamp=FIXED_TS),
            TextMessage(role=MessageRole.AGENT, text_content="Response", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        with patch(
            "devboard.agents.tools.conversation_tools.create_conversation_history_service",
            return_value=mock_history_service,
        ):
            tool = create_view_conversation_content_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42, include_thinking=False)

        assert "THINKING" not in result
        assert "AGENT: Response" in result

    @pytest.mark.asyncio
    async def test_include_thinking_true_shows_thinking(self, mock_conversation_repo, mock_conversation):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        events = [
            ThinkingEvent(thinking_text="secret thoughts", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        with patch(
            "devboard.agents.tools.conversation_tools.create_conversation_history_service",
            return_value=mock_history_service,
        ):
            tool = create_view_conversation_content_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42, include_thinking=True)

        assert "THINKING: secret thoughts" in result

    @pytest.mark.asyncio
    async def test_formats_tool_call_and_result(self, mock_conversation_repo, mock_conversation):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        events = [
            ToolCall(
                tool_call_id="tc1",
                tool_name="list_tasks",
                tool_args={"status": "planning"},
                timestamp=FIXED_TS,
            ),
            ToolResult(tool_call_id="tc1", result_content="some results", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        with patch(
            "devboard.agents.tools.conversation_tools.create_conversation_history_service",
            return_value=mock_history_service,
        ):
            tool = create_view_conversation_content_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42)

        assert "TOOL_CALL list_tasks" in result
        assert "status=planning" in result
        assert "→ RESULT: some results" in result

    @pytest.mark.asyncio
    async def test_since_last_user_message_filters_events(self, mock_conversation_repo, mock_conversation):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        events = [
            TextMessage(role=MessageRole.USER, text_content="first question", timestamp=FIXED_TS),
            TextMessage(role=MessageRole.AGENT, text_content="first answer", timestamp=FIXED_TS),
            TextMessage(role=MessageRole.USER, text_content="second question", timestamp=FIXED_TS),
            TextMessage(role=MessageRole.AGENT, text_content="second answer", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        with patch(
            "devboard.agents.tools.conversation_tools.create_conversation_history_service",
            return_value=mock_history_service,
        ):
            tool = create_view_conversation_content_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42, since_last_user_message=True)

        assert "first question" not in result
        assert "first answer" not in result
        assert "second question" in result
        assert "second answer" in result

    @pytest.mark.asyncio
    async def test_since_last_user_message_no_user_messages(self, mock_conversation_repo, mock_conversation):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        events = [
            TextMessage(role=MessageRole.AGENT, text_content="agent monologue", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        with patch(
            "devboard.agents.tools.conversation_tools.create_conversation_history_service",
            return_value=mock_history_service,
        ):
            tool = create_view_conversation_content_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42, since_last_user_message=True)

        # No user message found, so all events are returned
        assert "agent monologue" in result


# ──────────────────────────────────────────────
# create_view_agent_config_tool tests
# ──────────────────────────────────────────────


class TestCreateViewAgentConfigTool:
    @pytest.fixture
    def mock_document_repo(self):
        return Mock(spec=DocumentRepository)

    @pytest.fixture
    def mock_agent_config_service(self):
        return Mock()

    @pytest.fixture
    def mock_integration_service(self):
        return Mock()

    @pytest.fixture
    def mock_task_service(self):
        return Mock()

    @pytest.fixture
    def sample_config(self):
        return AgentConfigResponse(
            agent_role="task_planning",
            behaviour_guidelines="You are a planning agent.",
            context_content="Task context here.",
            custom_instructions="Be concise.",
            role_tools=[
                ToolInfo(name="list_tasks", description="List all tasks", source="role"),
                ToolInfo(name="view_task_details", description="View task details", source="role"),
            ],
            mcp_tools=[
                ToolInfo(name="gh_get_pr", description="Get PR info", source="mcp", server_name="github"),
            ],
            builtin_tools=[
                ToolInfo(name="web_search", source="builtin"),
            ],
        )

    def test_tool_creation(
        self,
        mock_conversation_repo,
        mock_document_repo,
        mock_agent_config_service,
        mock_integration_service,
        mock_task_service,
    ):
        tool = create_view_agent_config_tool(
            mock_conversation_repo,
            mock_document_repo,
            mock_agent_config_service,
            mock_integration_service,
            mock_task_service,
        )
        assert isinstance(tool, Tool)
        assert tool.name == "view_agent_config"

    @pytest.mark.asyncio
    async def test_not_found_raises_model_retry(
        self,
        mock_conversation_repo,
        mock_document_repo,
        mock_agent_config_service,
        mock_integration_service,
        mock_task_service,
    ):
        mock_conversation_repo.get_by_id.return_value = None

        tool = create_view_agent_config_tool(
            mock_conversation_repo,
            mock_document_repo,
            mock_agent_config_service,
            mock_integration_service,
            mock_task_service,
        )

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(conversation_id=99)

        assert "99" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_formats_agent_config(
        self,
        mock_conversation_repo,
        mock_conversation,
        mock_document_repo,
        mock_agent_config_service,
        mock_integration_service,
        mock_task_service,
        sample_config,
    ):
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        with patch(
            "devboard.agents.tools.conversation_tools.assemble_agent_config",
            new=AsyncMock(return_value=sample_config),
        ):
            tool = create_view_agent_config_tool(
                mock_conversation_repo,
                mock_document_repo,
                mock_agent_config_service,
                mock_integration_service,
                mock_task_service,
            )
            result = await tool.function(conversation_id=42)

        assert "Agent Role: task_planning" in result
        assert "Custom Instructions: Be concise." in result
        assert "Behaviour Guidelines" in result
        assert "You are a planning agent." in result
        assert "Context Content" in result
        assert "Task context here." in result
        assert "Role Tools" in result
        assert "list_tasks: List all tasks" in result
        assert "view_task_details: View task details" in result
        assert "MCP Tools" in result
        assert "gh_get_pr: Get PR info" in result
        assert "(server: github)" in result
        assert "Builtin Tools" in result
        assert "web_search" in result

    @pytest.mark.asyncio
    async def test_no_custom_instructions_shown(
        self,
        mock_conversation_repo,
        mock_conversation,
        mock_document_repo,
        mock_agent_config_service,
        mock_integration_service,
        mock_task_service,
    ):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        config = AgentConfigResponse(
            agent_role="project",
            behaviour_guidelines="System prompt.",
            context_content="",
            custom_instructions=None,
            role_tools=[],
            mcp_tools=[],
            builtin_tools=[],
        )

        with patch(
            "devboard.agents.tools.conversation_tools.assemble_agent_config",
            new=AsyncMock(return_value=config),
        ):
            tool = create_view_agent_config_tool(
                mock_conversation_repo,
                mock_document_repo,
                mock_agent_config_service,
                mock_integration_service,
                mock_task_service,
            )
            result = await tool.function(conversation_id=42)

        assert "Custom Instructions: (none)" in result

    @pytest.mark.asyncio
    async def test_input_schema_not_included(
        self,
        mock_conversation_repo,
        mock_conversation,
        mock_document_repo,
        mock_agent_config_service,
        mock_integration_service,
        mock_task_service,
    ):
        mock_conversation_repo.get_by_id.return_value = mock_conversation
        config = AgentConfigResponse(
            agent_role="project",
            behaviour_guidelines="System prompt.",
            context_content="",
            custom_instructions=None,
            role_tools=[
                ToolInfo(
                    name="my_tool",
                    description="A tool",
                    source="role",
                    input_schema={"type": "object", "properties": {"arg": {"type": "string"}}},
                )
            ],
            mcp_tools=[],
            builtin_tools=[],
        )

        with patch(
            "devboard.agents.tools.conversation_tools.assemble_agent_config",
            new=AsyncMock(return_value=config),
        ):
            tool = create_view_agent_config_tool(
                mock_conversation_repo,
                mock_document_repo,
                mock_agent_config_service,
                mock_integration_service,
                mock_task_service,
            )
            result = await tool.function(conversation_id=42)

        # Input schema should not be in the output
        assert "input_schema" not in result
        assert "properties" not in result
        assert "my_tool: A tool" in result


# ──────────────────────────────────────────────
# Test _format_events with tool_result_max_length parameter
# ──────────────────────────────────────────────


class TestFormatEventsWithToolResultMaxLength:
    def _ts(self) -> datetime.datetime:
        return FIXED_TS

    def test_tool_result_max_length_zero_excludes_tool_results(self):
        """Test that tool_result_max_length=0 excludes ToolResult events entirely."""
        events = [
            ToolCall(tool_call_id="tc1", tool_name="test_tool", tool_args=None, timestamp=self._ts()),
            ToolResult(tool_call_id="tc1", result_content="this should be excluded", timestamp=self._ts()),
            TextMessage(role=MessageRole.AGENT, text_content="Response", timestamp=self._ts()),
        ]
        result = _format_events(events, include_thinking=False, tool_result_max_length=0)

        assert "TOOL_CALL test_tool" in result
        assert "RESULT" not in result
        assert "this should be excluded" not in result
        assert "AGENT: Response" in result

    def test_tool_result_custom_max_length_truncates_to_length(self):
        """Test that custom tool_result_max_length truncates to that length."""
        long_result = "x" * 100
        events = [
            ToolResult(tool_call_id="tc1", result_content=long_result, timestamp=self._ts()),
        ]
        result = _format_events(events, include_thinking=False, tool_result_max_length=20)

        assert "→ RESULT:" in result
        assert long_result not in result  # Full result shouldn't be there
        assert "x" * 20 in result  # Truncated version should be there
        assert "..." in result  # Should have truncation marker

    def test_tool_result_default_max_length_unchanged(self):
        """Test that default tool_result_max_length behavior is unchanged."""
        long_result = "y" * 300
        events = [
            ToolResult(tool_call_id="tc1", result_content=long_result, timestamp=self._ts()),
        ]

        # Test with explicit default parameter
        result_explicit = _format_events(events, include_thinking=False, tool_result_max_length=200)

        # Test with no parameter (using default)
        result_default = _format_events(events, include_thinking=False)

        # Should behave the same
        assert result_explicit == result_default
        assert "→ RESULT:" in result_default
        assert "y" * 200 in result_default
        assert "..." in result_default

    def test_tool_result_short_content_not_truncated(self):
        """Test that short tool result content is not truncated."""
        short_result = "short result"
        events = [
            ToolResult(tool_call_id="tc1", result_content=short_result, timestamp=self._ts()),
        ]
        result = _format_events(events, include_thinking=False, tool_result_max_length=50)

        assert "→ RESULT: short result" in result
        assert "..." not in result


# ──────────────────────────────────────────────
# create_inspect_conversation_tool tests
# ──────────────────────────────────────────────


class TestCreateInspectConversationTool:
    def test_tool_creation(self, mock_conversation_repo):
        tool = create_inspect_conversation_tool(mock_conversation_repo)
        assert isinstance(tool, Tool)
        assert tool.name == "inspect_conversation"

    @pytest.mark.asyncio
    async def test_conversation_not_found_raises_model_retry(self, mock_conversation_repo):
        mock_conversation_repo.get_by_id.return_value = None

        tool = create_inspect_conversation_tool(mock_conversation_repo)

        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(conversation_id=999)

        assert "999" in str(exc_info.value)
        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_conversation_history_error_raises_model_retry(self, mock_conversation_repo, mock_conversation):
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        with patch(
            "devboard.agents.tools.conversation_tools.create_conversation_history_service",
            side_effect=HTTPException(status_code=400, detail="History error"),
        ):
            tool = create_inspect_conversation_tool(mock_conversation_repo)

            with pytest.raises(ModelRetry) as exc_info:
                await tool.function(conversation_id=42)

            assert "Cannot load conversation history" in str(exc_info.value)
            assert "History error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inspect_conversation_with_summary_mode(self, mock_conversation_repo, mock_conversation):
        """Test inspect_conversation in summary mode (no question provided)."""
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        # Mock conversation events
        events = [
            TextMessage(role=MessageRole.USER, text_content="Hello", timestamp=FIXED_TS),
            TextMessage(role=MessageRole.AGENT, text_content="Hi there!", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        # Mock ClaudeClient
        mock_claude_result = Mock()
        mock_claude_result.text_content = "This conversation shows a basic greeting exchange."
        mock_client = AsyncMock()
        mock_client.run.return_value = mock_claude_result

        with (
            patch(
                "devboard.agents.tools.conversation_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
            patch(
                "devboard.agents.tools.conversation_tools.ClaudeClient",
                return_value=mock_client,
            ) as mock_claude_class,
        ):
            tool = create_inspect_conversation_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42)

        # Verify ClaudeClient was configured correctly
        mock_claude_class.assert_called_once()
        call_kwargs = mock_claude_class.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
        assert call_kwargs["cwd"] == str(Path.home() / ".devboard")
        assert call_kwargs["load_settings"] is False
        assert "analyzing a conversation transcript" in call_kwargs["system_prompt"]

        # Verify the call to ClaudeClient.run
        mock_client.run.assert_called_once()
        run_args = mock_client.run.call_args[0][0]
        assert "provide a concise summary" in run_args
        assert "USER: Hello" in run_args
        assert "AGENT: Hi there!" in run_args

        # Verify result
        assert result == "This conversation shows a basic greeting exchange."

    @pytest.mark.asyncio
    async def test_inspect_conversation_with_question(self, mock_conversation_repo, mock_conversation):
        """Test inspect_conversation with specific question."""
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        events = [
            ToolCall(tool_call_id="tc1", tool_name="list_tasks", tool_args={"status": "planning"}, timestamp=FIXED_TS),
            ToolResult(tool_call_id="tc1", result_content="Task 1, Task 2", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        mock_claude_result = Mock()
        mock_claude_result.text_content = "The agent called list_tasks and found 2 planning tasks."
        mock_client = AsyncMock()
        mock_client.run.return_value = mock_claude_result

        with (
            patch(
                "devboard.agents.tools.conversation_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
            patch(
                "devboard.agents.tools.conversation_tools.ClaudeClient",
                return_value=mock_client,
            ),
        ):
            tool = create_inspect_conversation_tool(mock_conversation_repo)
            result = await tool.function(conversation_id=42, question="What tools were called?")

        # Verify the call to ClaudeClient.run includes the question
        mock_client.run.assert_called_once()
        run_args = mock_client.run.call_args[0][0]
        assert "What tools were called?" in run_args
        assert "answer the following question" in run_args
        assert "TOOL_CALL list_tasks" in run_args

        assert result == "The agent called list_tasks and found 2 planning tasks."

    @pytest.mark.asyncio
    async def test_inspect_conversation_custom_tool_result_max_length(self, mock_conversation_repo, mock_conversation):
        """Test inspect_conversation with custom tool_result_max_length."""
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        long_result = "x" * 500
        events = [
            ToolResult(tool_call_id="tc1", result_content=long_result, timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        mock_claude_result = Mock()
        mock_claude_result.text_content = "Analysis complete."
        mock_client = AsyncMock()
        mock_client.run.return_value = mock_claude_result

        with (
            patch(
                "devboard.agents.tools.conversation_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
            patch(
                "devboard.agents.tools.conversation_tools.ClaudeClient",
                return_value=mock_client,
            ),
        ):
            tool = create_inspect_conversation_tool(mock_conversation_repo)
            await tool.function(conversation_id=42, tool_result_max_length=50)

        # Verify that the formatted history was truncated appropriately
        mock_client.run.assert_called_once()
        run_args = mock_client.run.call_args[0][0]
        assert "x" * 500 not in run_args  # Full result shouldn't be there
        assert "x" * 50 in run_args  # Truncated version should be there

    @pytest.mark.asyncio
    async def test_inspect_conversation_excludes_thinking_events(self, mock_conversation_repo, mock_conversation):
        """Test that thinking events are excluded from the formatted history."""
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        events = [
            ThinkingEvent(thinking_text="secret thoughts", timestamp=FIXED_TS),
            TextMessage(role=MessageRole.AGENT, text_content="Response", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        mock_claude_result = Mock()
        mock_claude_result.text_content = "Analysis complete."
        mock_client = AsyncMock()
        mock_client.run.return_value = mock_claude_result

        with (
            patch(
                "devboard.agents.tools.conversation_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
            patch(
                "devboard.agents.tools.conversation_tools.ClaudeClient",
                return_value=mock_client,
            ),
        ):
            tool = create_inspect_conversation_tool(mock_conversation_repo)
            await tool.function(conversation_id=42)

        # Verify thinking events are excluded
        mock_client.run.assert_called_once()
        run_args = mock_client.run.call_args[0][0]
        assert "THINKING" not in run_args
        assert "secret thoughts" not in run_args
        assert "AGENT: Response" in run_args

    @pytest.mark.asyncio
    async def test_inspect_conversation_tool_result_max_length_zero(self, mock_conversation_repo, mock_conversation):
        """Test inspect_conversation with tool_result_max_length=0 excludes tool results."""
        mock_conversation_repo.get_by_id.return_value = mock_conversation

        events = [
            ToolCall(tool_call_id="tc1", tool_name="test_tool", tool_args=None, timestamp=FIXED_TS),
            ToolResult(tool_call_id="tc1", result_content="should be excluded", timestamp=FIXED_TS),
        ]
        history = ConversationHistory(messages=events)
        mock_history_service = AsyncMock()
        mock_history_service.get_conversation_history.return_value = history

        mock_claude_result = Mock()
        mock_claude_result.text_content = "Analysis complete."
        mock_client = AsyncMock()
        mock_client.run.return_value = mock_claude_result

        with (
            patch(
                "devboard.agents.tools.conversation_tools.create_conversation_history_service",
                return_value=mock_history_service,
            ),
            patch(
                "devboard.agents.tools.conversation_tools.ClaudeClient",
                return_value=mock_client,
            ),
        ):
            tool = create_inspect_conversation_tool(mock_conversation_repo)
            await tool.function(conversation_id=42, tool_result_max_length=0)

        # Verify tool results are excluded when tool_result_max_length=0
        mock_client.run.assert_called_once()
        run_args = mock_client.run.call_args[0][0]
        assert "TOOL_CALL test_tool" in run_args
        assert "RESULT" not in run_args
        assert "should be excluded" not in run_args
