"""Tests for title generator utility."""

from unittest.mock import AsyncMock, patch

import pytest

from devboard.agents.engines.claude_code.client import ClaudeCodeResult
from devboard.agents.title_generator import (
    ConversationTitleResult,
    TaskTitleResult,
    generate_conversation_title,
    generate_task_title_and_branch,
)
from devboard.services.project_directory import get_devboard_home


class TestGenerateTaskTitleAndBranch:
    """Tests for generate_task_title_and_branch function."""

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    async def test_successful_title_and_branch_generation(self, mock_client_class):
        """Test successful generation of task title and branch name."""
        prompt = "Add user authentication to the API"
        expected_result = TaskTitleResult(
            title="Add user authentication to API",
            branch_name="add-user-authentication-api",
        )

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.return_value = ClaudeCodeResult(
            text_content="Generated title and branch",
            result_message=AsyncMock(),
            session_id="test-session",
            structured_output=expected_result,
        )

        result = await generate_task_title_and_branch(prompt)

        assert result == TaskTitleResult(
            title="Add user authentication to API",
            branch_name="add-user-authentication-api",
        )

        mock_client_class.assert_called_once()
        call_args = mock_client_class.call_args
        assert call_args.kwargs["model"] == "haiku"
        assert call_args.kwargs["load_settings"] is False
        assert call_args.kwargs["sandbox_enabled"] is False
        assert call_args.kwargs["output_model"] is TaskTitleResult
        assert call_args.kwargs["effort"] == "low"
        assert call_args.kwargs["cwd"] == str(get_devboard_home())
        mock_client.run.assert_called_once_with(prompt)

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    async def test_missing_structured_output_fallback(self, mock_client_class):
        """Test fallback when structured_output is None."""
        prompt = "Fix the broken login form validation"

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.return_value = ClaudeCodeResult(
            text_content="Some response text",
            result_message=AsyncMock(),
            session_id="test-session",
            structured_output=None,
        )

        result = await generate_task_title_and_branch(prompt)

        assert result.title == prompt  # Prompt is under 80 chars
        assert result.branch_name.startswith("task-")
        assert result.branch_name.replace("task-", "").isdigit()

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    async def test_client_exception_fallback(self, mock_client_class):
        """Test fallback when ClaudeClient raises an exception."""
        prompt = "Implement new feature"

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.side_effect = Exception("API error")

        result = await generate_task_title_and_branch(prompt)

        assert result.title == prompt
        assert result.branch_name.startswith("task-")

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    @patch("devboard.agents.title_generator.time.time")
    async def test_long_prompt_truncation_fallback(self, mock_time, mock_client_class):
        """Test fallback with long prompt that needs truncation."""
        long_prompt = "A" * 100  # 100 characters, over the 80 char limit
        mock_time.return_value = 1234567890

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.return_value = ClaudeCodeResult(
            text_content="Some response text",
            result_message=AsyncMock(),
            session_id="test-session",
            structured_output=None,
        )

        result = await generate_task_title_and_branch(long_prompt)

        assert result.title == "A" * 77 + "..."
        assert result.branch_name == "task-1234567890"


class TestGenerateConversationTitle:
    """Tests for generate_conversation_title function."""

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    async def test_successful_conversation_title_generation(self, mock_client_class):
        """Test successful generation of conversation title."""
        prompt = "Can you help me debug the login flow issue?"
        expected_result = ConversationTitleResult(title="Debug Login Flow Issue")

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.return_value = ClaudeCodeResult(
            text_content="Generated title",
            result_message=AsyncMock(),
            session_id="test-session",
            structured_output=expected_result,
        )

        result = await generate_conversation_title(prompt)

        assert result == "Debug Login Flow Issue"

        mock_client_class.assert_called_once()
        call_args = mock_client_class.call_args
        assert call_args.kwargs["model"] == "haiku"
        assert call_args.kwargs["load_settings"] is False
        assert call_args.kwargs["sandbox_enabled"] is False
        assert call_args.kwargs["output_model"] is ConversationTitleResult
        assert call_args.kwargs["effort"] == "low"
        assert call_args.kwargs["cwd"] == str(get_devboard_home())
        mock_client.run.assert_called_once_with(prompt)

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    async def test_missing_structured_output_fallback(self, mock_client_class):
        """Test fallback when structured_output is None."""
        prompt = "Help with project setup"

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.return_value = ClaudeCodeResult(
            text_content="Some response text",
            result_message=AsyncMock(),
            session_id="test-session",
            structured_output=None,
        )

        result = await generate_conversation_title(prompt)

        assert result == prompt  # Prompt is under 60 chars

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    async def test_client_exception_fallback(self, mock_client_class):
        """Test fallback when ClaudeClient raises an exception."""
        prompt = "Review code changes"

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.side_effect = Exception("Network error")

        result = await generate_conversation_title(prompt)

        assert result == prompt

    @pytest.mark.asyncio
    @patch("devboard.agents.title_generator.ClaudeClient")
    async def test_long_prompt_truncation_fallback(self, mock_client_class):
        """Test fallback with long prompt that needs truncation."""
        long_prompt = "B" * 70  # 70 characters, over the 60 char limit

        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.run.return_value = ClaudeCodeResult(
            text_content="Some response text",
            result_message=AsyncMock(),
            session_id="test-session",
            structured_output=None,
        )

        result = await generate_conversation_title(long_prompt)

        assert result == "B" * 57 + "..."
