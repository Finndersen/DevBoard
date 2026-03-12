"""Tests for ClaudeCodeSessionService."""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from devboard.agents.engines.claude_code.session import (
    AssistantSessionMessage,
    ClaudeCodeSessionMigrator,
    ClaudeCodeSessionService,
    MetaSessionMessage,
    UserSessionMessage,
)
from devboard.agents.engines.claude_code.session.file_locator import (
    find_all_session_todo_files,
    find_main_session_todo_file,
    find_session_file,
    find_sub_agent_session_file,
)
from devboard.agents.engines.claude_code.session.parser import is_message_entry, parse_session_message
from devboard.agents.events import MetaMessageType
from devboard.api.schemas.claude_code_todo import TodoPriority, TodoStatus


class TestClaudeCodeSessionService:
    """Test suite for ClaudeCodeSessionService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return ClaudeCodeSessionService()

    def test_parse_user_message(self):
        """Test parsing a user message from JSONL."""
        entry = {
            "type": "user",
            "uuid": "user-msg-1",
            "timestamp": "2025-10-08T15:10:57.769Z",
            "isSidechain": False,
            "message": {"role": "user", "content": "What is the current directory?"},
        }

        session_msg = parse_session_message(entry, line_num=1)

        assert isinstance(session_msg, UserSessionMessage)
        assert session_msg.text_content == "What is the current directory?"
        assert session_msg.timestamp.year == 2025
        assert session_msg.line_num == 1

    def test_parse_user_message_no_meta_flags(self):
        """Test that regular user messages produce a UserSessionMessage (not MetaSessionMessage)."""
        entry = {
            "type": "user",
            "uuid": "user-msg-plain",
            "timestamp": "2025-10-08T15:10:57.769Z",
            "isSidechain": False,
            "message": {"role": "user", "content": "Hello there!"},
        }

        session_msg = parse_session_message(entry, line_num=1)

        assert isinstance(session_msg, UserSessionMessage)

    def test_parse_user_message_compact_summary(self):
        """Test parsing a user message with isCompactSummary flag produces MetaSessionMessage."""
        entry = {
            "type": "user",
            "uuid": "user-compact-1",
            "timestamp": "2025-10-08T15:10:57.769Z",
            "isSidechain": False,
            "isCompactSummary": True,
            "message": {"role": "user", "content": "Summary of conversation so far..."},
        }

        session_msg = parse_session_message(entry, line_num=5)

        assert isinstance(session_msg, MetaSessionMessage)
        assert session_msg.meta_type == MetaMessageType.COMPACT_SUMMARY
        assert session_msg.text_content == "Summary of conversation so far..."

    def test_parse_user_message_meta(self):
        """Test parsing a user message with isMeta flag produces MetaSessionMessage."""
        entry = {
            "type": "user",
            "uuid": "user-meta-1",
            "timestamp": "2025-10-08T15:10:57.769Z",
            "isSidechain": False,
            "isMeta": True,
            "message": {"role": "user", "content": "Skill prompt content here..."},
        }

        session_msg = parse_session_message(entry, line_num=6)

        assert isinstance(session_msg, MetaSessionMessage)
        assert session_msg.meta_type == MetaMessageType.SKILL_CONTENT
        assert session_msg.text_content == "Skill prompt content here..."

    def test_parse_user_message_meta_list_of_text_blocks(self):
        """Test parsing an isMeta message where content is a list of text blocks (Claude Code JSONL format)."""
        entry = {
            "type": "user",
            "uuid": "user-meta-2",
            "timestamp": "2025-10-08T15:10:57.769Z",
            "isSidechain": False,
            "isMeta": True,
            "message": {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First skill block."},
                    {"type": "text", "text": "Second skill block."},
                ],
            },
        }

        session_msg = parse_session_message(entry, line_num=7)

        assert isinstance(session_msg, MetaSessionMessage)
        assert session_msg.meta_type == MetaMessageType.SKILL_CONTENT
        assert session_msg.text_content == "First skill block.\nSecond skill block."

    def test_parse_assistant_text_message(self):
        """Test parsing an assistant message with text content."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-1",
            "timestamp": "2025-10-08T15:11:00.401Z",
            "isSidechain": False,
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "/Users/test/projects/TestProject"}],
            },
        }

        session_msg = parse_session_message(entry, line_num=2)

        assert isinstance(session_msg, AssistantSessionMessage)
        assert session_msg.text_content == "/Users/test/projects/TestProject"
        assert session_msg.line_num == 2

    def test_parse_assistant_multiple_text_blocks(self):
        """Test parsing assistant message with multiple text blocks."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-2",
            "timestamp": "2025-10-08T15:12:00.000Z",
            "isSidechain": False,
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First part."},
                    {"type": "text", "text": "Second part."},
                ],
            },
        }

        session_msg = parse_session_message(entry, line_num=3)

        assert session_msg is not None
        assert session_msg.text_content == "First part.\nSecond part."
        assert session_msg.line_num == 3

    def test_parse_assistant_with_tool_call(self):
        """Test parsing assistant message with only tool calls (no text content)."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-3",
            "timestamp": "2025-10-08T15:13:00.000Z",
            "isSidechain": False,
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

        session_msg = parse_session_message(entry, line_num=4)
        assert session_msg is not None
        assert session_msg.text_content == ""
        assert len(session_msg.tool_calls) == 1
        assert session_msg.line_num == 4

    def test_parse_assistant_mixed_text_and_tool(self):
        """Test parsing assistant message with both text and tool calls."""
        entry = {
            "type": "assistant",
            "uuid": "asst-msg-4",
            "timestamp": "2025-10-08T15:14:00.000Z",
            "isSidechain": False,
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

        session_msg = parse_session_message(entry, line_num=5)

        assert session_msg is not None
        assert session_msg.text_content == "Let me check that."
        assert len(session_msg.tool_calls) == 1
        assert session_msg.line_num == 5

    def test_is_message_entry_filters_non_messages(self):
        """Test that non-message entries are filtered out by is_message_entry."""
        assert not is_message_entry({"type": "summary", "summary": "text", "leafUuid": "uuid-123"})
        assert not is_message_entry({"type": "queue-operation", "operation": "dequeue"})
        assert not is_message_entry({})
        assert is_message_entry({"type": "user"})
        assert is_message_entry({"type": "assistant"})

    def test_parse_tool_result(self):
        """Test parsing tool result messages."""
        entry = {
            "type": "user",
            "uuid": "user-msg-2",
            "timestamp": "2025-10-08T15:15:00.000Z",
            "isSidechain": False,
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

        session_msg = parse_session_message(entry, line_num=7)
        assert session_msg is not None
        assert len(session_msg.tool_results) == 1
        assert session_msg.line_num == 7

    def test_load_session_messages(self, service):
        """Test loading full session message history from JSONL file."""
        jsonl_data = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-10-08T15:10:00.000Z",
                "isSidechain": False,
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-10-08T15:10:01.000Z",
                "isSidechain": False,
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}]},
            },
            {"type": "summary", "summary": "Greeting", "leafUuid": "s1"},
            {
                "type": "user",
                "uuid": "u2",
                "timestamp": "2025-10-08T15:10:05.000Z",
                "isSidechain": False,
                "message": {"role": "user", "content": "How are you?"},
            },
            {
                "type": "assistant",
                "uuid": "a2",
                "timestamp": "2025-10-08T15:10:06.000Z",
                "isSidechain": False,
                "message": {"role": "assistant", "content": [{"type": "text", "text": "I'm doing well!"}]},
            },
        ]

        jsonl_content = "\n".join(json.dumps(entry) for entry in jsonl_data)
        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("devboard.agents.engines.claude_code.session.service.find_session_file", return_value=session_file):
            with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
                session_messages = service.load_session_messages("test-session")

        assert len(session_messages) == 4  # 2 user + 2 assistant, summary filtered out
        assert isinstance(session_messages[0], UserSessionMessage)
        assert session_messages[0].text_content == "Hello"
        assert session_messages[0].line_num == 1
        assert isinstance(session_messages[1], AssistantSessionMessage)
        assert session_messages[1].text_content == "Hi there!"
        assert session_messages[1].line_num == 2
        assert isinstance(session_messages[2], UserSessionMessage)
        assert session_messages[2].text_content == "How are you?"
        assert session_messages[2].line_num == 4  # Line 3 was summary, skipped
        assert isinstance(session_messages[3], AssistantSessionMessage)
        assert session_messages[3].text_content == "I'm doing well!"
        assert session_messages[3].line_num == 5

    def test_get_last_session_message_skips_non_message_entries(self, service):
        """Test that get_last_session_message skips non-message entries like queue-operation."""
        jsonl_data = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-10-08T15:10:00.000Z",
                "isSidechain": False,
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-10-08T15:10:01.000Z",
                "isSidechain": False,
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi there!"}]},
            },
            {
                "type": "queue-operation",
                "operation": "dequeue",
                "timestamp": "2025-10-08T15:10:02.000Z",
                "sessionId": "test-session",
            },
        ]

        jsonl_content = "\n".join(json.dumps(entry) for entry in jsonl_data)
        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("devboard.agents.engines.claude_code.session.service.find_session_file", return_value=session_file):
            with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
                message = service.get_last_session_message("test-session")

        assert isinstance(message, AssistantSessionMessage)
        assert message.text_content == "Hi there!"
        assert message.line_num == 2

    def test_load_conversation_file_not_found(self, service):
        """Test error handling when session file doesn't exist."""
        with patch(
            "devboard.agents.engines.claude_code.session.service.find_session_file",
            side_effect=FileNotFoundError("Session file not found"),
        ):
            with pytest.raises(FileNotFoundError, match="Session file not found"):
                service.load_session_messages("non-existent-session")

    def test_load_conversation_malformed_json(self, service):
        """Test handling of malformed JSONL entries."""
        jsonl_content = """{"type":"user","uuid":"u1","timestamp":"2025-10-08T15:10:00.000Z","isSidechain":false,"message":{"content":"Valid"}}
        {malformed json}
        {"type":"user","uuid":"u2","timestamp":"2025-10-08T15:10:02.000Z","isSidechain":false,"message":{"content":"Also valid"}}"""

        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("devboard.agents.engines.claude_code.session.service.find_session_file", return_value=session_file):
            with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
                session_messages = service.load_session_messages("test-session")

        # Should have 2 messages (malformed one skipped)
        assert len(session_messages) == 2

    def test_load_conversation_permission_error(self, service):
        """Test handling of permission errors."""
        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("devboard.agents.engines.claude_code.session.service.find_session_file", return_value=session_file):
            with patch("pathlib.Path.open", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError, match="Access denied"):
                    service.load_session_messages("test-session")

    def test_find_session_file_found(self):
        """Test finding session file across project directories."""
        session_id = "abc-123-def"
        claude_projects_dir = Path("/home/user/.claude/projects")
        session_file = claude_projects_dir / "project2" / f"{session_id}.jsonl"

        with patch("devboard.agents.engines.claude_code.session.file_locator.Path.exists", return_value=True):
            with patch.object(Path, "glob", return_value=[session_file]):
                with patch.object(Path, "is_file", return_value=True):
                    result = find_session_file(session_id, claude_projects_dir)
                    assert result == session_file

    def test_find_session_file_not_found(self):
        """Test finding session file when it doesn't exist."""
        session_id = "nonexistent-session"
        claude_projects_dir = Path("/home/user/.claude/projects")

        with patch("devboard.agents.engines.claude_code.session.file_locator.Path.exists", return_value=True):
            with patch.object(Path, "glob", return_value=[]):
                with pytest.raises(FileNotFoundError, match="Session file not found"):
                    find_session_file(session_id, claude_projects_dir)

    def test_find_session_file_no_claude_dir(self):
        """Test finding session file when Claude projects directory doesn't exist."""
        session_id = "test-session"
        claude_projects_dir = Path("/home/user/.claude/projects")

        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Claude Code projects directory not found"):
                find_session_file(session_id, claude_projects_dir)

    def test_load_conversation_with_find(self, service):
        """Test loading session messages using find_session_file."""
        session_id = "test-session"
        jsonl_data = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-10-08T15:10:00.000Z",
                "isSidechain": False,
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-10-08T15:10:01.000Z",
                "isSidechain": False,
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi!"}]},
            },
        ]

        jsonl_content = "\n".join(json.dumps(entry) for entry in jsonl_data)
        session_file = Path("/home/user/.claude/projects/project1") / f"{session_id}.jsonl"

        with patch("devboard.agents.engines.claude_code.session.service.find_session_file", return_value=session_file):
            with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
                session_messages = service.load_session_messages(session_id)

        assert len(session_messages) == 2
        assert session_messages[0].text_content == "Hello"
        assert session_messages[1].text_content == "Hi!"

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

        with patch.object(service, "claude_todos_dir", Path("/home/user/.claude/todos")):
            with patch.object(Path, "exists", return_value=True):
                with patch("pathlib.Path.open", mock_open(read_data=todo_content)):
                    todos = service.load_todo_list(session_id)

        assert len(todos) == 3

        assert todos[0].content == "Run tests"
        assert todos[0].status == TodoStatus.COMPLETED
        assert todos[0].active_form == "Running tests"
        assert todos[0].priority == TodoPriority.HIGH
        assert todos[0].id == "1"

        assert todos[1].content == "Fix linting errors"
        assert todos[1].status == TodoStatus.IN_PROGRESS
        assert todos[1].active_form == "Fixing linting errors"
        assert todos[1].priority is None
        assert todos[1].id is None

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

        main_file = Path(f"/home/user/.claude/todos/{session_id}-agent-{session_id}.json")
        sub_file = Path(f"/home/user/.claude/todos/{session_id}-agent-{subagent_id}.json")

        def mock_open_todos(file_path, *args, **kwargs):
            if session_id + ".json" in str(file_path):
                return mock_open(read_data=json.dumps(main_todos))()
            else:
                return mock_open(read_data=json.dumps(sub_todos))()

        with patch(
            "devboard.agents.engines.claude_code.session.service.find_all_session_todo_files",
            return_value=[main_file, sub_file],
        ):
            with patch("pathlib.Path.open", mock_open_todos):
                todos = service.load_todo_list(session_id, include_subagents=True)

        assert len(todos) == 2
        assert todos[0].content == "Main task"
        assert todos[0].status == TodoStatus.COMPLETED
        assert todos[1].content == "Sub task"
        assert todos[1].status == TodoStatus.IN_PROGRESS

    def test_find_main_session_todo_file(self):
        """Test finding main session todo file."""
        session_id = "abc-123"
        claude_todos_dir = Path("/home/user/.claude/todos")
        expected_filename = f"{session_id}-agent-{session_id}.json"

        with patch.object(Path, "exists", return_value=True):
            result = find_main_session_todo_file(session_id, claude_todos_dir)

        assert result.name == expected_filename

    def test_find_main_session_todo_file_not_found(self):
        """Test error when main session todo file doesn't exist."""
        session_id = "nonexistent"
        claude_todos_dir = Path("/home/user/.claude/todos")

        with patch.object(Path, "exists", side_effect=[True, False]):
            with pytest.raises(FileNotFoundError, match="Main session todo file not found"):
                find_main_session_todo_file(session_id, claude_todos_dir)

    def test_find_main_session_todo_file_no_todos_dir(self):
        """Test error when todos directory doesn't exist."""
        session_id = "test-session"
        claude_todos_dir = Path("/home/user/.claude/todos")

        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Claude Code todos directory not found"):
                find_main_session_todo_file(session_id, claude_todos_dir)

    def test_find_all_session_todo_files(self):
        """Test finding all todo files for a session."""
        session_id = "parent-123"
        sub1 = "sub-agent-1"
        sub2 = "sub-agent-2"
        claude_todos_dir = Path("/home/user/.claude/todos")

        expected_files = [
            Path(f"/home/user/.claude/todos/{session_id}-agent-{session_id}.json"),
            Path(f"/home/user/.claude/todos/{session_id}-agent-{sub1}.json"),
            Path(f"/home/user/.claude/todos/{session_id}-agent-{sub2}.json"),
        ]

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "glob", return_value=expected_files):
                result = find_all_session_todo_files(session_id, claude_todos_dir)

        assert len(result) == 3
        assert all(isinstance(p, Path) for p in result)

    def test_find_all_session_todo_files_no_todos_dir(self):
        """Test finding todos when todos directory doesn't exist."""
        session_id = "test-session"
        claude_todos_dir = Path("/home/user/.claude/todos")

        with patch.object(Path, "exists", return_value=False):
            result = find_all_session_todo_files(session_id, claude_todos_dir)

        assert result == []

    def test_find_sub_agent_session_file_found(self, tmp_path):
        """Test finding a sub-agent session file with correct path derivation."""
        session_id = "parent-session-123"
        agent_id = "ac2a274"
        claude_projects_dir = tmp_path / "projects"
        project_dir = claude_projects_dir / "my-project"
        project_dir.mkdir(parents=True)

        # Create parent session file
        parent_file = project_dir / f"{session_id}.jsonl"
        parent_file.write_text("{}")

        # Create sub-agent file
        subagents_dir = project_dir / session_id / "subagents"
        subagents_dir.mkdir(parents=True)
        sub_agent_file = subagents_dir / f"agent-{agent_id}.jsonl"
        sub_agent_file.write_text("{}")

        result = find_sub_agent_session_file(session_id, agent_id, claude_projects_dir)
        assert result == sub_agent_file

    def test_find_sub_agent_session_file_not_found(self, tmp_path):
        """Test FileNotFoundError when sub-agent file doesn't exist."""
        session_id = "parent-session-123"
        agent_id = "nonexistent"
        claude_projects_dir = tmp_path / "projects"
        project_dir = claude_projects_dir / "my-project"
        project_dir.mkdir(parents=True)

        parent_file = project_dir / f"{session_id}.jsonl"
        parent_file.write_text("{}")

        with pytest.raises(FileNotFoundError, match="Sub-agent session file not found"):
            find_sub_agent_session_file(session_id, agent_id, claude_projects_dir)

    def test_find_sub_agent_session_file_rejects_path_traversal(self):
        """Test that agent IDs with path traversal characters are rejected."""
        claude_projects_dir = Path("/home/user/.claude/projects")

        with pytest.raises(ValueError, match="Invalid agent_id"):
            find_sub_agent_session_file("parent-session", "../../../etc/passwd", claude_projects_dir)

        with pytest.raises(ValueError, match="Invalid agent_id"):
            find_sub_agent_session_file("parent-session", "agent/../../secret", claude_projects_dir)

        with pytest.raises(ValueError, match="Invalid agent_id"):
            find_sub_agent_session_file("parent-session", "agent.id", claude_projects_dir)

    def test_find_sub_agent_session_file_valid_agent_ids(self, tmp_path):
        """Test that valid agent IDs are accepted."""
        session_id = "parent-session"
        claude_projects_dir = tmp_path / "projects"
        project_dir = claude_projects_dir / "my-project"
        project_dir.mkdir(parents=True)

        parent_file = project_dir / f"{session_id}.jsonl"
        parent_file.write_text("{}")

        for valid_id in ["ac2a274", "abc-123", "AGENT1", "a1b2c3"]:
            subagents_dir = project_dir / session_id / "subagents"
            subagents_dir.mkdir(parents=True, exist_ok=True)
            sub_file = subagents_dir / f"agent-{valid_id}.jsonl"
            sub_file.write_text("{}")

            result = find_sub_agent_session_file(session_id, valid_id, claude_projects_dir)
            assert result == sub_file

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


class TestEncodePathForClaudeProjects:
    """Tests for ClaudeCodeSessionMigrator.encode_path_for_claude_projects."""

    def test_encodes_simple_path(self):
        result = ClaudeCodeSessionMigrator.encode_path_for_claude_projects("/Users/foo/myproject")
        assert result == "-Users-foo-myproject"

    def test_replaces_dots(self):
        result = ClaudeCodeSessionMigrator.encode_path_for_claude_projects("/Users/foo/my.project")
        assert result == "-Users-foo-my-project"

    def test_replaces_underscores(self):
        """Underscores must be encoded as dashes to match Claude CLI behaviour."""
        result = ClaudeCodeSessionMigrator.encode_path_for_claude_projects(
            "/Users/finn.andersen/.devboard/worktrees/1_DevBoard.worktree-4"
        )
        assert result == "-Users-finn-andersen--devboard-worktrees-1-DevBoard-worktree-4"


class TestClaudeCodeSessionMigratorExtractCwd:
    """Tests for ClaudeCodeSessionMigrator._extract_cwd_from_session_file."""

    @pytest.fixture
    def migrator(self):
        """Create migrator instance."""
        return ClaudeCodeSessionMigrator()

    def test_extract_cwd_from_session_file_valid(self, migrator):
        """Test extracting cwd from a valid JSONL file with cwd entries."""
        jsonl_data = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-10-08T15:10:00.000Z",
                "isSidechain": False,
                "cwd": "/Users/test/projects/MyProject",
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-10-08T15:10:01.000Z",
                "isSidechain": False,
                "cwd": "/Users/test/projects/MyProject",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Hi!"}]},
            },
        ]

        jsonl_content = "\n".join(json.dumps(entry) for entry in jsonl_data)
        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
            result = migrator._extract_cwd_from_session_file(session_file)

        assert result == "/Users/test/projects/MyProject"

    def test_extract_cwd_from_session_file_no_cwd_entry(self, migrator):
        """Test ValueError when no cwd entry exists."""
        jsonl_data = [
            {"type": "summary", "summary": "Some summary", "leafUuid": "uuid-1"},
            {"type": "summary", "summary": "Another summary", "leafUuid": "uuid-2"},
        ]

        jsonl_content = "\n".join(json.dumps(entry) for entry in jsonl_data)
        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
            with pytest.raises(ValueError, match="No 'cwd' entry found in session file"):
                migrator._extract_cwd_from_session_file(session_file)

    def test_extract_cwd_from_session_file_skips_malformed_lines(self, migrator):
        """Test that malformed JSON lines are skipped and cwd is still extracted."""
        jsonl_content = (
            "{malformed json}\n"
            '{"type": "summary", "summary": "Some summary"}\n'
            '{"type": "user", "uuid": "u1", "cwd": "/Users/test/valid/path", "message": {"content": "Hello"}}'
        )

        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("pathlib.Path.open", mock_open(read_data=jsonl_content)):
            result = migrator._extract_cwd_from_session_file(session_file)

        assert result == "/Users/test/valid/path"

    def test_extract_cwd_from_session_file_empty_file(self, migrator):
        """Test ValueError when file is empty."""
        session_file = Path("/home/user/.claude/projects/project1/test-session.jsonl")

        with patch("pathlib.Path.open", mock_open(read_data="")):
            with pytest.raises(ValueError, match="No 'cwd' entry found in session file"):
                migrator._extract_cwd_from_session_file(session_file)


@pytest.mark.asyncio
class TestMigrateSessionToDirectory:
    """Test suite for ClaudeCodeSessionMigrator.migrate_session_to_directory method."""

    @pytest.fixture
    def migrator(self):
        """Create migrator instance."""
        return ClaudeCodeSessionMigrator()

    async def test_migrate_session_replaces_paths_in_content(self, migrator, tmp_path):
        """Test that migrating a session file replaces paths inside the content."""
        old_working_dir = "/Users/test/projects/OldProject"
        new_working_dir = "/Users/test/projects/NewProject"
        session_id = "test-session-abc123"

        old_encoded = migrator.encode_path_for_claude_projects(old_working_dir)
        new_encoded = migrator.encode_path_for_claude_projects(new_working_dir)
        old_project_dir = tmp_path / old_encoded
        new_project_dir = tmp_path / new_encoded
        old_project_dir.mkdir(parents=True)

        session_file = old_project_dir / f"{session_id}.jsonl"
        jsonl_entries = [
            {
                "type": "user",
                "uuid": "u1",
                "timestamp": "2025-10-08T15:10:00.000Z",
                "isSidechain": False,
                "cwd": old_working_dir,
                "sessionId": session_id,
                "message": {"role": "user", "content": "Hello"},
            },
            {
                "type": "assistant",
                "uuid": "a1",
                "timestamp": "2025-10-08T15:10:01.000Z",
                "isSidechain": False,
                "cwd": old_working_dir,
                "sessionId": session_id,
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"Working in {old_working_dir}"}],
                },
            },
        ]
        session_file.write_text("\n".join(json.dumps(entry) for entry in jsonl_entries))

        migrator.claude_projects_dir = tmp_path

        result = await migrator.migrate_session_to_directory(session_id, new_working_dir)

        assert result == new_project_dir / f"{session_id}.jsonl"
        assert result.exists()
        assert not session_file.exists()

        content = result.read_text()
        assert old_working_dir not in content
        assert new_working_dir in content

        lines = content.strip().split("\n")
        for line in lines:
            entry = json.loads(line)
            assert entry["cwd"] == new_working_dir

    async def test_migrate_session_skips_when_already_in_correct_location(self, migrator, tmp_path):
        """Test that migration returns None when file is already in correct location."""
        working_dir = "/Users/test/projects/Project"
        session_id = "test-session-xyz"

        encoded = migrator.encode_path_for_claude_projects(working_dir)
        project_dir = tmp_path / encoded
        project_dir.mkdir(parents=True)

        session_file = project_dir / f"{session_id}.jsonl"
        session_file.write_text('{"type": "user", "cwd": "/Users/test/projects/Project"}')

        migrator.claude_projects_dir = tmp_path

        result = await migrator.migrate_session_to_directory(session_id, working_dir)

        assert result is None
        assert session_file.exists()

    async def test_migrate_session_moves_session_directory(self, migrator, tmp_path):
        """Test that the session directory (containing tool-results) is also moved."""
        old_working_dir = "/Users/test/projects/Old"
        new_working_dir = "/Users/test/projects/New"
        session_id = "session-with-dir"

        old_encoded = migrator.encode_path_for_claude_projects(old_working_dir)
        old_project_dir = tmp_path / old_encoded
        old_project_dir.mkdir(parents=True)

        session_file = old_project_dir / f"{session_id}.jsonl"
        session_file.write_text(f'{{"type": "user", "cwd": "{old_working_dir}"}}')

        old_session_dir = old_project_dir / session_id
        old_session_dir.mkdir()
        tool_result_file = old_session_dir / "tool-result.txt"
        tool_result_file.write_text("some tool output")

        migrator.claude_projects_dir = tmp_path

        new_encoded = migrator.encode_path_for_claude_projects(new_working_dir)
        new_project_dir = tmp_path / new_encoded

        await migrator.migrate_session_to_directory(session_id, new_working_dir)

        new_session_dir = new_project_dir / session_id
        assert new_session_dir.exists()
        assert (new_session_dir / "tool-result.txt").exists()
        assert not old_session_dir.exists()
