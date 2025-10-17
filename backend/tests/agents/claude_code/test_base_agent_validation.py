"""Tests for BaseClaudeAgent validation and retry logic."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from claude_agent_sdk import ResultMessage

from devboard.agents.engines.claude_code.base_agent import (
    MAX_RETRY_ATTEMPTS,
    ClaudeCodeAgent,
    MessageResponse,
)
from devboard.agents.engines.claude_code.client import ClaudeCodeResult
from devboard.agents.engines.claude_code.virtual_tools import (
    EditDocumentArgs,
    EditDocumentTool,
    VirtualToolRequests,
)
from devboard.agents.language_models import LanguageModel, LLMProvider, ModelType
from devboard.db.models.task import Task


def create_mock_result(text_content: str, session_id: str = "test-session") -> ClaudeCodeResult:
    """Helper to create a ClaudeCodeResult with mock ResultMessage."""
    mock_result_message = Mock(spec=ResultMessage)
    mock_result_message.session_id = session_id
    return ClaudeCodeResult(
        text_content=text_content,
        result_message=mock_result_message,
        session_id=session_id,
    )


class MockAgent(ClaudeCodeAgent):
    """Mock implementation of BaseClaudeAgent for testing."""

    def __init__(self, task, document_repo, virtual_tools=None, model=None):
        self._test_virtual_tools = virtual_tools or []
        if model is None:
            model = LanguageModel(
                provider=LLMProvider.ANTHROPIC,
                name="claude-sonnet-4",
                type=ModelType.REASONING,
                full_name="claude-sonnet-4-20250514",
            )
        super().__init__(task, document_repo, model)

    def _get_role_description(self) -> str:
        return "Test agent role description"

    def _get_state_context(self) -> str:
        return "Test state context"

    def _get_virtual_tools(self):
        return self._test_virtual_tools


@pytest.fixture
def mock_task():
    """Create a mock task."""
    task = Mock(spec=Task)
    task.specification = Mock()
    task.specification.content = "Test content"
    task.specification.document_type = Mock(value="task_specification")
    task.implementation_plan = Mock()
    task.implementation_plan.content = ""
    task.implementation_plan.document_type = Mock(value="task_implementation_plan")
    return task


@pytest.fixture
def mock_document_repo():
    """Create a mock document repository."""
    return Mock()


@pytest.fixture
def mock_edit_tool():
    """Create a mock edit tool."""
    tool = Mock(spec=EditDocumentTool)
    tool.tool_name = "edit_task_specification"
    tool.args_model = EditDocumentArgs
    tool.execute = AsyncMock(return_value="Edit successful")
    tool.get_schema = Mock(return_value="Mock tool schema")
    return tool


@pytest.fixture
def test_agent(mock_task, mock_document_repo, mock_edit_tool):
    """Create a test agent with a mock tool."""
    return MockAgent(mock_task, mock_document_repo, virtual_tools=[mock_edit_tool])


class TestValidMessageResponse:
    """Tests for valid message responses."""

    @pytest.mark.asyncio
    async def test_parse_valid_message_response(self, test_agent):
        """Test parsing a plain text message response."""
        result = create_mock_result("Hello, world!")

        response = await test_agent._parse_response(result, retry_count=0)

        assert isinstance(response, MessageResponse)
        assert response.content == "Hello, world!"
        assert response.session_id == "test-session"


class TestValidToolCallResponse:
    """Tests for valid tool call responses."""

    @pytest.mark.asyncio
    async def test_parse_valid_tool_call_response(self, test_agent):
        """Test parsing a valid tool call response."""
        result = create_mock_result(
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "edit_task_specification",
                    "arguments": {
                        "edits": [{"find": "old text", "replace": "new text"}],
                        "reasoning": "Test reasoning",
                    },
                }
            )
        )

        response = await test_agent._parse_response(result, retry_count=0)

        assert isinstance(response, VirtualToolRequests)
        assert len(response.calls) == 1
        assert response.calls[0].tool_name == "edit_task_specification"
        assert response.calls[0].arguments["edits"][0]["find"] == "old text"
        assert response.session_id == "test-session"


class TestInvalidJSONResponse:
    """Tests for invalid JSON responses - now treated as normal messages."""

    @pytest.mark.asyncio
    async def test_invalid_json_treated_as_message(self, test_agent):
        """Test that non-JSON responses are treated as normal messages (no retry)."""
        result = create_mock_result("This is not JSON at all")

        response = await test_agent._parse_response(result, retry_count=0)

        # Non-JSON is now treated as a normal text message
        assert isinstance(response, MessageResponse)
        assert response.content == "This is not JSON at all"
        assert response.session_id == "test-session"

    @pytest.mark.asyncio
    async def test_plain_text_message_no_validation(self, test_agent):
        """Test that plain text messages work without JSON format."""
        result = create_mock_result("Hello! I've analyzed the task and here's what I found...")

        response = await test_agent._parse_response(result, retry_count=0)

        # Plain text should work fine as normal message
        assert isinstance(response, MessageResponse)
        assert "Hello! I've analyzed" in response.content
        assert response.session_id == "test-session"


class TestInvalidResponseStructure:
    """Tests for JSON structures that trigger validation and retry."""

    @pytest.mark.asyncio
    async def test_json_array_treated_as_message(self, test_agent):
        """Test that JSON array (not object) is treated as normal message."""
        result = create_mock_result('["array", "not", "object"]')

        response = await test_agent._parse_response(result, retry_count=0)

        # JSON array should be treated as plain text message
        assert isinstance(response, MessageResponse)
        assert response.content == '["array", "not", "object"]'
        assert response.session_id == "test-session"

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_json_object_without_tool_fields_triggers_retry(self, mock_run, test_agent):
        """Test that JSON object without tool_name/arguments triggers validation error and retry."""
        result = create_mock_result('{"content": "Hello", "no_tool_fields": true}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        # JSON object should trigger validation and retry
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid tool call response format" in call_args.kwargs["prompt_or_approvals"]
        assert call_args.kwargs["_retry_count"] == 1


class TestInvalidMessageFormat:
    """Tests for JSON objects that fail validation."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_json_object_triggers_validation(self, mock_run, test_agent):
        """Test that JSON object triggers validation (and retry if invalid)."""
        result = create_mock_result('{"type": "message"}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        # JSON object should trigger validation and retry
        mock_run.assert_called_once()
        assert "ERROR: Invalid tool call response format" in mock_run.call_args.kwargs["prompt_or_approvals"]

    @pytest.mark.asyncio
    async def test_message_with_content_works(self, test_agent):
        """Test that plain text message works correctly."""
        result = create_mock_result("Test message")

        response = await test_agent._parse_response(result, retry_count=0)

        # Should return full text
        assert isinstance(response, MessageResponse)
        assert response.content == "Test message"
        assert response.session_id == "test-session"


class TestInvalidToolCallFormat:
    """Tests for invalid tool call format validation."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_tool_call_missing_tool_name_triggers_retry(self, mock_run, test_agent):
        """Test that JSON with arguments but no tool_name triggers a retry."""
        result = create_mock_result('{"arguments": {}}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        # JSON object should trigger validation and retry
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid tool call response format" in call_args.kwargs["prompt_or_approvals"]

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_tool_call_missing_arguments_triggers_retry(self, mock_run, test_agent):
        """Test that JSON with tool_name but no arguments triggers a retry."""
        result = create_mock_result('{"tool_name": "edit_task_specification"}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        # JSON object should trigger validation and retry
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid tool call response format" in call_args.kwargs["prompt_or_approvals"]

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_tool_call_invalid_structure_triggers_retry(self, mock_run, test_agent):
        """Test that tool call with invalid structure triggers a retry."""
        # Tool call detected (has tool_name and arguments) but structure is invalid
        result = create_mock_result('{"tool_name": "edit_task_specification", "arguments": "not a dict"}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # Check keyword argument
        assert "ERROR: Invalid tool call response format" in call_args.kwargs["prompt_or_approvals"]
        assert call_args.kwargs["_retry_count"] == 1

    @pytest.mark.asyncio
    async def test_tool_call_validation_max_retries_raises_error(self, test_agent):
        """Test that tool call validation raises error after max retries."""
        result = create_mock_result('{"tool_name": "edit_task_specification", "arguments": "not a dict"}')

        with pytest.raises(ValueError) as exc_info:
            await test_agent._parse_response(result, retry_count=MAX_RETRY_ATTEMPTS)

        assert "Tool call validation failed after" in str(exc_info.value)
        assert str(MAX_RETRY_ATTEMPTS) in str(exc_info.value)


class TestUnknownTool:
    """Tests for unknown tool validation."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_unknown_tool_triggers_retry(self, mock_run, test_agent):
        """Test that unknown tool name triggers a retry with available tools list."""
        result = create_mock_result(
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "nonexistent_tool",
                    "arguments": {},
                }
            )
        )

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # Check keyword argument
        assert "ERROR: Unknown tool 'nonexistent_tool'" in call_args.kwargs["prompt_or_approvals"]
        assert "Available tools:" in call_args.kwargs["prompt_or_approvals"]
        assert "edit_task_specification" in call_args.kwargs["prompt_or_approvals"]
        assert call_args.kwargs["_retry_count"] == 1

    @pytest.mark.asyncio
    async def test_unknown_tool_max_retries_raises_error(self, test_agent):
        """Test that unknown tool raises error after max retries."""
        result = create_mock_result(
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "nonexistent_tool",
                    "arguments": {},
                }
            )
        )

        with pytest.raises(ValueError) as exc_info:
            await test_agent._parse_response(result, retry_count=MAX_RETRY_ATTEMPTS)

        assert "Unknown tool 'nonexistent_tool' after" in str(exc_info.value)
        assert str(MAX_RETRY_ATTEMPTS) in str(exc_info.value)


class TestInvalidToolArguments:
    """Tests for invalid tool argument validation."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_invalid_tool_arguments_trigger_retry(self, mock_run, test_agent):
        """Test that invalid tool arguments trigger a retry with validation errors."""
        result = create_mock_result(
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "edit_task_specification",
                    "arguments": {
                        # Missing required 'edits' field
                        "reasoning": "Test reasoning",
                    },
                }
            )
        )

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # Check keyword argument
        assert "ERROR: Invalid arguments for tool 'edit_task_specification'" in call_args.kwargs["prompt_or_approvals"]
        assert "Validation errors:" in call_args.kwargs["prompt_or_approvals"]
        assert call_args.kwargs["_retry_count"] == 1

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_wrong_type_arguments_trigger_retry(self, mock_run, test_agent):
        """Test that arguments with wrong types trigger a retry."""
        result = create_mock_result(
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "edit_task_specification",
                    "arguments": {
                        "edits": "not a list",  # Should be a list
                        "reasoning": "Test reasoning",
                    },
                }
            )
        )

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # Check keyword argument
        assert "ERROR: Invalid arguments for tool 'edit_task_specification'" in call_args.kwargs["prompt_or_approvals"]
        assert "Validation errors:" in call_args.kwargs["prompt_or_approvals"]

    @pytest.mark.asyncio
    async def test_invalid_arguments_max_retries_raises_error(self, test_agent):
        """Test that invalid arguments raise error after max retries."""
        result = create_mock_result(
            json.dumps(
                {
                    "type": "tool_call",
                    "tool_name": "edit_task_specification",
                    "arguments": {
                        "edits": "not a list",
                    },
                }
            )
        )

        with pytest.raises(ValueError) as exc_info:
            await test_agent._parse_response(result, retry_count=MAX_RETRY_ATTEMPTS)

        assert "Tool arguments validation failed for 'edit_task_specification' after" in str(exc_info.value)
        assert str(MAX_RETRY_ATTEMPTS) in str(exc_info.value)


class TestRetryMechanism:
    """Tests for the retry mechanism."""

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.base_agent.ClaudeClient")
    async def test_run_increments_retry_count(self, mock_client_class, test_agent):
        """Test that run() properly increments retry count."""
        # Create mock client instance
        mock_client = MagicMock()
        mock_client.run = AsyncMock(return_value=create_mock_result("Success"))
        mock_client_class.return_value = mock_client

        # Call run with retry count (using new parameter name)
        response = await test_agent.run(
            prompt_or_approvals="Test message",
            session_id="test-session",
            _retry_count=2,
        )

        # Verify response is valid
        assert isinstance(response, MessageResponse)
        assert response.content == "Success"

    @pytest.mark.asyncio
    @patch("devboard.agents.engines.claude_code.base_agent.ClaudeClient")
    async def test_run_creates_new_client_each_time(self, mock_client_class, test_agent):
        """Test that run() creates a new client on each call (for fresh system prompt)."""
        mock_client = MagicMock()
        mock_client.run = AsyncMock(return_value=create_mock_result("Success"))
        mock_client_class.return_value = mock_client

        # Call run twice (using new parameter name)
        await test_agent.run(prompt_or_approvals="Message 1", session_id="test-session")
        await test_agent.run(prompt_or_approvals="Message 2", session_id="test-session")

        # Verify client was created twice
        assert mock_client_class.call_count == 2
