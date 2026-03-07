"""Todo list parsing for Claude Code session todo files."""

import json
from pathlib import Path

import logfire

from devboard.api.schemas.claude_code_todo import TodoItem


def load_todo_list_from_file(todo_file: Path) -> list[TodoItem]:
    """Load and parse todo items from a single todo JSON file.

    Raises:
        json.JSONDecodeError: If the todo file contains invalid JSON
    """
    try:
        content = todo_file.read_text().strip()
    except OSError as e:
        logfire.error(f"Failed to read todo file {todo_file}: {e}")
        raise

    if not content or content == "[]":
        return []

    try:
        todos_data = json.loads(content)
    except json.JSONDecodeError as e:
        logfire.error(f"Failed to parse todo file {todo_file}: {e}")
        raise

    todos: list[TodoItem] = []
    for todo_data in todos_data:
        if "activeForm" in todo_data:
            todo_data["active_form"] = todo_data.pop("activeForm")
        todos.append(TodoItem(**todo_data))

    return todos
