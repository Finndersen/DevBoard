"""Tests for ClaudeCodeSessionService."""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from devboard.api.schemas.agent_conversation import MessageRole
from devboard.services.claude_code_session import ClaudeCodeSessionService


class TestClaudeCodeSessionService:
    """Test suite for ClaudeCodeSessionService."""

    @pytest.fixture
    def service(self):
        """Create service with test project directory."""
        return ClaudeCodeSessionService(Path("/Users/test/projects/TestProject"))

    def test_normalize_path(self):
        """Test path normalization for Claude Code directory names."""
        path = Path("/Users/finn/projects/DevBoard")
        normalized = ClaudeCodeSessionService._normalize_path(path)
        assert normalized == "-Users-finn-projects-DevBoard"

    def test_get_session_file_path(self, service):
        """Test session file path resolution."""
        session_id = "abc-123-def"
        expected_path = (
            Path.home()
            / ".claude"
            / "projects"
            / "-Users-test-projects-TestProject"
            / "abc-123-def.jsonl"
        )

        result = service.get_session_file_path(session_id)
        assert result == expected_path

    def test_parse_user_message(self, service):
        """Test parsing a user message from JSONL."""
        entry = {
            "type": "user",
            "uuid": "user-msg-1",
            "timestamp": "2025-10-08T15:10:57.769Z",
            "message": {"role": "user", "content": "What is the current directory?"},
        }

        message = service._parse_jsonl_entry(entry)

        assert message is not None
        assert message.role == MessageRole.USER
        assert message.text_content == "What is the current directory?"
        assert message.timestamp.year == 2025

    def test_parse_assistant_text_message(self, service):
        """Test parsing an assistant message with text content."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-1",
            "timestamp": "2025-10-08T15:11:00.401Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "/Users/test/projects/TestProject"}],
            },
        }

        message = service._parse_jsonl_entry(entry)

        assert message is not None
        assert message.role == MessageRole.AGENT
        assert message.text_content == "/Users/test/projects/TestProject"

    def test_parse_assistant_multiple_text_blocks(self, service):
        """Test parsing assistant message with multiple text blocks."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-2",
            "timestamp": "2025-10-08T15:12:00.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First part."},
                    {"type": "text", "text": "Second part."},
                ],
            },
        }

        message = service._parse_jsonl_entry(entry)

        assert message is not None
        assert message.text_content == "First part.\nSecond part."

    def test_parse_assistant_with_tool_call_filtered(self, service):
        """Test that assistant messages with only tool calls are filtered out."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-3",
            "timestamp": "2025-10-08T15:13:00.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "Bash",
                        "input": {"command": "ls"},
                    }
                ],
            },
        }

        message = service._parse_jsonl_entry(entry)
        assert message is None

    def test_parse_assistant_mixed_text_and_tool(self, service):
        """Test parsing assistant message with both text and tool calls."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-4",
            "timestamp": "2025-10-08T15:14:00.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me check that."},
                    {
                        "type": "tool_use",
                        "id": "toolu_456",
                        "name": "Bash",
                        "input": {"command": "ls"},
                    },
                ],
            },
        }

        message = service._parse_jsonl_entry(entry)

        assert message is not None
        assert message.text_content == "Let me check that."

    def test_parse_summary_filtered(self, service):
        """Test that summary messages are filtered out."""
        entry = {
            "type": "summary",
            "summary": "Some conversation summary",
            "leafUuid": "uuid-123",
        }

        message = service._parse_jsonl_entry(entry)
        assert message is None

    def test_parse_tool_result_filtered(self, service):
        """Test that tool result messages are filtered out."""
        entry = {
            "type": "user",
            "uuid": "user-msg-2",
            "timestamp": "2025-10-08T15:15:00.000Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": "result data",
                    }
                ],
            },
        }

        message = service._parse_jsonl_entry(entry)
        assert message is None

    def test_load_conversation_history(self, service):
        """Test loading full conversation history from JSONL file."""
        jsonl_data = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-10-08T15:10:00.000Z",
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-10-08T15:10:01.000Z",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}]},
            },
            {"type": "summary", "summary": "Greeting", "leafUuid": "s1"},
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-10-08T15:10:05.000Z",
                "message": {"role": "user", "content": "How are you?"},
            },
            {
                "type": "assistant",
                "uuid": "a2",
                "timestamp": "2025-10-08T15:10:06.000Z",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "I'm doing well!"}]},
            },
        ]

        jsonl_content = "\n".join(json.dumps(entry) for entry in jsonl_data)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
                messages = service.load_conversation_history("test-session")

        assert len(messages) == 4  # 2 user + 2 assistant, summary filtered out
        assert messages[0].role == MessageRole.USER
        assert messages[0].text_content == "Hello"
        assert messages[1].role == MessageRole.AGENT
        assert messages[1].text_content == "Hi there!"
        assert messages[2].role == MessageRole.USER
        assert messages[2].text_content == "How are you?"
        assert messages[3].role == MessageRole.AGENT
        assert messages[3].text_content == "I'm doing well!"

    def test_load_conversation_file_not_found(self, service):
        """Test error handling when session file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Session file not found"):
                service.load_conversation_history("non-existent-session")

    def test_load_conversation_malformed_json(self, service):
        """Test handling of malformed JSONL entries."""
        jsonl_content = """{"type":"user","message":{"content":"Valid"}}
        {malformed json}
        {"type":"user","message":{"content":"Also valid"}}"""

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
                # Should skip malformed entry and continue
                messages = service.load_conversation_history("test-session")

        # Should have 2 messages (malformed one skipped)
        assert len(messages) == 2

    def test_load_conversation_permission_error(self, service):
        """Test handling of permission errors."""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError, match="Permission denied reading session file"):
                    service.load_conversation_history("test-session")
