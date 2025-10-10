"""Tests for ClaudeCodeSessionService."""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from devboard.agents.claude_code.session import ClaudeCodeSessionService
from devboard.api.schemas.agent_conversation import MessageRole
from devboard.api.schemas.claude_code_todo import TodoPriority, TodoStatus


class TestClaudeCodeSessionService:
    """Test suite for ClaudeCodeSessionService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return ClaudeCodeSessionService()

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
        with patch.object(service, "find_session_file", side_effect=FileNotFoundError("Session file not found")):
            with pytest.raises(FileNotFoundError, match="Session file not found"):
                service.load_conversation_history("non-existent-session")

    def test_load_conversation_malformed_json(self, service):
        """Test handling of malformed JSONL entries."""
        jsonl_content = """{"type":"user","timestamp":"2025-10-08T15:10:00.000Z","message":{"content":"Valid"}}
        {malformed json}
        {"type":"user","timestamp":"2025-10-08T15:10:02.000Z","message":{"content":"Also valid"}}"""

        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch.object(service, "find_session_file", return_value=session_file):
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

    def test_find_session_file_found(self, service):
        """Test finding session file across project directories."""
        session_id = "abc-123-def"
        session_file = Path("/home/user/.claude/projects/project2") / f"{session_id}.jsonl"

        # Mock find_session_file to return the path
        with patch.object(service, "find_session_file", return_value=session_file):
            result = service.find_session_file(session_id)
            assert result == session_file

    def test_find_session_file_not_found(self, service):
        """Test finding session file when it doesn't exist."""
        session_id = "nonexistent-session"

        # Mock find_session_file to raise FileNotFoundError
        with patch.object(service, "find_session_file", side_effect=FileNotFoundError("Session file not found")):
            with pytest.raises(FileNotFoundError, match="Session file not found"):
                service.find_session_file(session_id)

    def test_find_session_file_no_claude_dir(self, service):
        """Test finding session file when Claude projects directory doesn't exist."""
        session_id = "test-session"

        # Mock claude_projects_dir.exists() to return False
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Claude Code projects directory not found"):
                service.find_session_file(session_id)

    def test_load_conversation_with_find(self, service):
        """Test loading conversation using find_session_file."""
        session_id = "test-session"
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
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi!"}]},
            },
        ]

        jsonl_content = "\n".join(json.dumps(entry) for entry in jsonl_data)
        session_file = Path("/home/user/.claude/projects/project1") / f"{session_id}.jsonl"

        # Mock find_session_file to return a path
        with patch.object(service, "find_session_file", return_value=session_file):
            with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
                messages = service.load_conversation_history(session_id)

        assert len(messages) == 2
        assert messages[0].text_content == "Hello"
        assert messages[1].text_content == "Hi!"

    def test_load_todo_list_with_content(self, service):
        """Test loading todo list with multiple items."""
        session_id = "test-session-123"
        todo_data = [
            {
                "content": "Run tests",
                "status": "completed",
                "activeForm": "Running tests",
                "priority": "high",
                "id": "1",
            },
            {
                "content": "Fix linting errors",
                "status": "in_progress",
                "activeForm": "Fixing linting errors",
            },
            {"content": "Update documentation", "status": "pending"},
        ]

        todo_content = json.dumps(todo_data)
        todo_file = Path(f"/home/user/.claude/todos/{session_id}-agent-{session_id}.json")

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                with patch("pathlib.Path.open", mock_open(read_data=todo_content)):
                    todos = service.load_todo_list(session_id)

        assert len(todos) == 3

        # First todo with all fields
        assert todos[0].content == "Run tests"
        assert todos[0].status == TodoStatus.COMPLETED
        assert todos[0].active_form == "Running tests"
        assert todos[0].priority == TodoPriority.HIGH
        assert todos[0].id == "1"

        # Second todo without priority and id
        assert todos[1].content == "Fix linting errors"
        assert todos[1].status == TodoStatus.IN_PROGRESS
        assert todos[1].active_form == "Fixing linting errors"
        assert todos[1].priority is None
        assert todos[1].id is None

        # Third todo with minimal fields
        assert todos[2].content == "Update documentation"
        assert todos[2].status == TodoStatus.PENDING
        assert todos[2].active_form is None
        assert todos[2].priority is None

    def test_load_todo_list_empty_file(self, service):
        """Test loading an empty todo file."""
        session_id = "test-session-456"

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                with patch("pathlib.Path.open", mock_open(read_data="[]")):
                    todos = service.load_todo_list(session_id)

        assert todos == []

    def test_load_todo_list_no_file(self, service):
        """Test loading todos when file doesn't exist."""
        session_id = "nonexistent-session"

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", side_effect=lambda: False):
                todos = service.load_todo_list(session_id)

        assert todos == []

    def test_load_todo_list_malformed_json(self, service):
        """Test handling malformed JSON in todo file."""
        session_id = "test-session-789"

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                with patch("pathlib.Path.open", mock_open(read_data="{malformed json")):
                    with pytest.raises(json.JSONDecodeError):
                        service.load_todo_list(session_id)

    def test_load_todo_list_with_subagents(self, service):
        """Test loading todos including sub-agent todos."""
        session_id = "parent-session"
        subagent_id = "sub-agent-123"

        main_todos = [{"content": "Main task", "status": "completed"}]
        sub_todos = [{"content": "Sub task", "status": "in_progress"}]

        # Mock find_all_session_todo_files to return both files
        main_file = Path(f"/home/user/.claude/todos/{session_id}-agent-{session_id}.json")
        sub_file = Path(f"/home/user/.claude/todos/{session_id}-agent-{subagent_id}.json")

        def mock_open_todos(file_path, *args, **kwargs):
            if session_id + ".json" in str(file_path):
                return mock_open(read_data=json.dumps(main_todos))()
            else:
                return mock_open(read_data=json.dumps(sub_todos))()

        with patch.object(service, "find_all_session_todo_files", return_value=[main_file, sub_file]):
            with patch("pathlib.Path.open", mock_open_todos):
                todos = service.load_todo_list(session_id, include_subagents=True)

        assert len(todos) == 2
        assert todos[0].content == "Main task"
        assert todos[0].status == TodoStatus.COMPLETED
        assert todos[1].content == "Sub task"
        assert todos[1].status == TodoStatus.IN_PROGRESS

    def test_find_main_session_todo_file(self, service):
        """Test finding main session todo file."""
        session_id = "abc-123"
        expected_filename = f"{session_id}-agent-{session_id}.json"

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                result = service.find_main_session_todo_file(session_id)

        assert result.name == expected_filename

    def test_find_main_session_todo_file_not_found(self, service):
        """Test error when main session todo file doesn't exist."""
        session_id = "nonexistent"

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            # First exists() is for todos_dir, second is for the file
            with patch.object(Path, "exists", side_effect=[True, False]):
                with pytest.raises(FileNotFoundError, match="Main session todo file not found"):
                    service.find_main_session_todo_file(session_id)

    def test_find_main_session_todo_file_no_todos_dir(self, service):
        """Test error when todos directory doesn't exist."""
        session_id = "test-session"

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=False):
                with pytest.raises(FileNotFoundError, match="Claude Code todos directory not found"):
                    service.find_main_session_todo_file(session_id)

    def test_find_all_session_todo_files(self, service):
        """Test finding all todo files for a session."""
        session_id = "parent-123"
        sub1 = "sub-agent-1"
        sub2 = "sub-agent-2"

        expected_files = [
            Path(f"/home/user/.claude/todos/{session_id}-agent-{session_id}.json"),
            Path(f"/home/user/.claude/todos/{session_id}-agent-{sub1}.json"),
            Path(f"/home/user/.claude/todos/{session_id}-agent-{sub2}.json"),
        ]

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "glob", return_value=expected_files):
                    result = service.find_all_session_todo_files(session_id)

        assert len(result) == 3
        assert all(isinstance(p, Path) for p in result)

    def test_find_all_session_todo_files_no_todos_dir(self, service):
        """Test finding todos when todos directory doesn't exist."""
        session_id = "test-session"

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=False):
                result = service.find_all_session_todo_files(session_id)

        assert result == []

    def test_todo_status_enum_values(self, service):
        """Test all TodoStatus enum values can be parsed."""
        session_id = "status-test"
        todo_data = [
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "in_progress"},
            {"content": "Task 3", "status": "completed"},
        ]

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                with patch("pathlib.Path.open", mock_open(read_data=json.dumps(todo_data))):
                    todos = service.load_todo_list(session_id)

        assert todos[0].status == TodoStatus.PENDING
        assert todos[1].status == TodoStatus.IN_PROGRESS
        assert todos[2].status == TodoStatus.COMPLETED

    def test_todo_priority_enum_values(self, service):
        """Test all TodoPriority enum values can be parsed."""
        session_id = "priority-test"
        todo_data = [
            {"content": "Task 1", "status": "pending", "priority": "high"},
            {"content": "Task 2", "status": "pending", "priority": "medium"},
            {"content": "Task 3", "status": "pending", "priority": "low"},
        ]

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                with patch("pathlib.Path.open", mock_open(read_data=json.dumps(todo_data))):
                    todos = service.load_todo_list(session_id)

        assert todos[0].priority == TodoPriority.HIGH
        assert todos[1].priority == TodoPriority.MEDIUM
        assert todos[2].priority == TodoPriority.LOW
