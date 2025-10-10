"""Schemas for Claude Code todo items.

Claude Code maintains todo lists in JSON files at ~/.claude/todos/ to track
task progress during agent execution.
"""

from enum import Enum

from pydantic import BaseModel


class TodoStatus(str, Enum):
    """Status of a todo item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TodoPriority(str, Enum):
    """Priority level of a todo item."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TodoItem(BaseModel):
    """A single todo item from Claude Code's todo list.

    Todo items track task progress during agent execution. They include
    the task description (content), current status, and optional metadata
    like priority and a present-continuous form for displaying active tasks.
    """

    content: str
    """Description of the task (imperative form, e.g., 'Run tests')"""

    status: TodoStatus
    """Current status of the task"""

    active_form: str | None = None
    """Present continuous form for display during execution (e.g., 'Running tests')"""

    priority: TodoPriority | None = None
    """Priority level of the task"""

    id: str | None = None
    """Optional unique identifier for the task"""
