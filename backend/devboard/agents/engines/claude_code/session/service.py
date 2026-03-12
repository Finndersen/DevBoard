"""Service for reading and parsing Claude Code session history."""

from pathlib import Path

from devboard.agents.engines.claude_code.session.file_locator import (
    find_all_session_todo_files,
    find_main_session_todo_file,
    find_session_file,
    find_sub_agent_session_file,
)
from devboard.agents.engines.claude_code.session.models import (
    SessionMessage,
)
from devboard.agents.engines.claude_code.session.parser import (
    get_last_session_message_from_file,
    load_session_messages_from_file,
)
from devboard.agents.engines.claude_code.session.todo_parser import load_todo_list_from_file
from devboard.api.schemas.claude_code_todo import TodoItem


class ClaudeCodeSessionService:
    """Service for reading and parsing Claude Code session history."""

    def __init__(self):
        self.claude_projects_dir = Path.home() / ".claude" / "projects"
        self.claude_todos_dir = Path.home() / ".claude" / "todos"

    def get_last_session_message(self, session_id: str) -> SessionMessage | None:
        session_file = find_session_file(session_id, self.claude_projects_dir)
        return get_last_session_message_from_file(session_file)

    def load_session_messages(self, session_id: str) -> list[SessionMessage]:
        session_file = find_session_file(session_id, self.claude_projects_dir)
        return load_session_messages_from_file(session_file)

    def load_sub_agent_session_messages(self, parent_session_id: str, agent_id: str) -> list[SessionMessage]:
        sub_agent_file = find_sub_agent_session_file(parent_session_id, agent_id, self.claude_projects_dir)
        return load_session_messages_from_file(sub_agent_file)

    def load_todo_list(self, session_id: str, include_subagents: bool = False) -> list[TodoItem]:
        if include_subagents:
            todo_files = find_all_session_todo_files(session_id, self.claude_todos_dir)
        else:
            try:
                main_todo_file = find_main_session_todo_file(session_id, self.claude_todos_dir)
                todo_files = [main_todo_file]
            except FileNotFoundError:
                return []
        todos = []
        for todo_file in todo_files:
            todos.extend(load_todo_list_from_file(todo_file))
        return todos
