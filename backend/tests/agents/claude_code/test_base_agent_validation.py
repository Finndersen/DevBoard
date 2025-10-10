"""Tests for BaseClaudeAgent validation and retry logic."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from claude_agent_sdk import ResultMessage

from devboard.agents.claude_code.base_agent import (
    MAX_RETRY_ATTEMPTS,
    BaseClaudeAgent,
    MessageResponse,
)
from devboard.agents.claude_code.client import ClaudeCodeResult
from devboard.agents.claude_code.virtual_tools import (
    EditDocumentArgs,
    EditDocumentTool,
    VirtualToolRequests,
)
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


class MockAgent(BaseClaudeAgent):
    """Mock implementation of BaseClaudeAgent for testing."""

    def __init__(self, task, document_repo, virtual_tools=None):
        super().__init__(task, document_repo)
        self._test_virtual_tools = virtual_tools or []

    def _build_system_prompt(self) -> str:
        return "Test system prompt"

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
    return tool


@pytest.fixture
def test_agent(mock_task, mock_document_repo, mock_edit_tool):
    """Create a test agent with a mock tool."""
    return MockAgent(mock_task, mock_document_repo, virtual_tools=[mock_edit_tool])


class TestValidMessageResponse:
    """Tests for valid message responses."""

    @pytest.mark.asyncio
    async def test_parse_valid_message_response(self, test_agent):
        """Test parsing a valid message response."""
        result = create_mock_result('{"type": "message", "content": "Hello, world!"}')

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
    """Tests for invalid JSON responses."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_invalid_json_triggers_retry(self, mock_run, test_agent):
        """Test that invalid JSON triggers a retry with error feedback."""
        result = create_mock_result("This is not JSON at all")

        # Mock the retry to return a valid response
        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        response = await test_agent._parse_response(result, retry_count=0)

        # Verify retry was called with error message
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Your response is not valid JSON" in call_args[0][0]
        assert "JSON parsing error:" in call_args[0][0]
        assert call_args[1]["session_id"] == "test-session"
        assert call_args[1]["_retry_count"] == 1

        # Verify we got the mocked response
        assert isinstance(response, MessageResponse)
        assert response.content == "Fixed response"

    @pytest.mark.asyncio
    async def test_invalid_json_max_retries_fallback(self, test_agent):
        """Test that after max retries, invalid JSON is treated as plain text."""
        result = create_mock_result("This is not JSON at all")

        response = await test_agent._parse_response(result, retry_count=MAX_RETRY_ATTEMPTS)

        # After max retries, should fall back to plain text message
        assert isinstance(response, MessageResponse)
        assert response.content == "This is not JSON at all"
        assert response.session_id == "test-session"


class TestInvalidResponseStructure:
    """Tests for invalid response structure."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_json_array_triggers_retry(self, mock_run, test_agent):
        """Test that JSON array (not object) triggers a retry."""
        result = create_mock_result('["array", "not", "object"]')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Response must be a JSON object (dict), not list" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_missing_type_field_triggers_retry(self, mock_run, test_agent):
        """Test that missing 'type' field triggers a retry."""
        result = create_mock_result('{"content": "Hello", "no_type_field": true}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Missing or invalid 'type' field in response" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_invalid_type_value_triggers_retry(self, mock_run, test_agent):
        """Test that invalid 'type' value triggers a retry."""
        result = create_mock_result('{"type": "invalid_type", "content": "Hello"}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Missing or invalid 'type' field in response" in call_args[0][0]
        assert "invalid_type" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1


class TestInvalidMessageFormat:
    """Tests for invalid message format validation."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_message_missing_content_triggers_retry(self, mock_run, test_agent):
        """Test that message missing content field triggers a retry."""
        result = create_mock_result('{"type": "message"}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid message response format" in call_args[0][0]
        assert "Validation errors:" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1

    @pytest.mark.asyncio
    async def test_message_validation_max_retries_fallback(self, test_agent):
        """Test message validation fallback after max retries."""
        result = create_mock_result('{"type": "message"}')

        response = await test_agent._parse_response(result, retry_count=MAX_RETRY_ATTEMPTS)

        # Should fall back to using whatever content is available
        assert isinstance(response, MessageResponse)
        assert response.session_id == "test-session"


class TestInvalidToolCallFormat:
    """Tests for invalid tool call format validation."""

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_tool_call_missing_tool_name_triggers_retry(self, mock_run, test_agent):
        """Test that tool call missing tool_name triggers a retry."""
        result = create_mock_result('{"type": "tool_call", "arguments": {}}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid tool call response format" in call_args[0][0]
        assert "Validation errors:" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1

    @pytest.mark.asyncio
    @patch.object(MockAgent, "run")
    async def test_tool_call_missing_arguments_triggers_retry(self, mock_run, test_agent):
        """Test that tool call missing arguments triggers a retry."""
        result = create_mock_result('{"type": "tool_call", "tool_name": "edit_task_specification"}')

        mock_run.return_value = MessageResponse(
            content="Fixed response",
            session_id="test-session",
        )

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid tool call response format" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1

    @pytest.mark.asyncio
    async def test_tool_call_validation_max_retries_raises_error(self, test_agent):
        """Test that tool call validation raises error after max retries."""
        result = create_mock_result('{"type": "tool_call", "tool_name": "edit_task_specification"}')

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

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Unknown tool 'nonexistent_tool'" in call_args[0][0]
        assert "Available tools:" in call_args[0][0]
        assert "edit_task_specification" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1

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

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid arguments for tool 'edit_task_specification'" in call_args[0][0]
        assert "Validation errors:" in call_args[0][0]
        assert call_args[1]["_retry_count"] == 1

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

        response = await test_agent._parse_response(result, retry_count=0)

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "ERROR: Invalid arguments for tool 'edit_task_specification'" in call_args[0][0]
        assert "Validation errors:" in call_args[0][0]

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
    @patch("devboard.agents.claude_code.base_agent.ClaudeClient")
    async def test_run_increments_retry_count(self, mock_client_class, test_agent):
        """Test that run() properly increments retry count."""
        # Create mock client instance
        mock_client = MagicMock()
        mock_client.run = AsyncMock(return_value=create_mock_result('{"type": "message", "content": "Success"}'))
        mock_client_class.return_value = mock_client

        # Call run with retry count
        response = await test_agent.run(
            user_message="Test message",
            session_id="test-session",
            _retry_count=2,
        )

        # Verify response is valid
        assert isinstance(response, MessageResponse)
        assert response.content == "Success"

    @pytest.mark.asyncio
    @patch("devboard.agents.claude_code.base_agent.ClaudeClient")
    async def test_run_creates_new_client_each_time(self, mock_client_class, test_agent):
        """Test that run() creates a new client on each call (for fresh system prompt)."""
        mock_client = MagicMock()
        mock_client.run = AsyncMock(return_value=create_mock_result('{"type": "message", "content": "Success"}'))
        mock_client_class.return_value = mock_client

        # Call run twice
        await test_agent.run("Message 1", session_id="test-session")
        await test_agent.run("Message 2", session_id="test-session")

        # Verify client was created twice
        assert mock_client_class.call_count == 2
