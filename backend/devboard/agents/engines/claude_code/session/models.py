"""Session message dataclasses for Claude Code sessions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from devboard.agents.engines.claude_code.session.types import (
    TextBlockDict,
    ThinkingBlockDict,
    ToolResultBlockDict,
    ToolUseBlockDict,
)
from devboard.agents.events import LocalCommandType, MetaMessageType


@dataclass
class BaseSessionMessage:
    """Common fields for all session message types."""

    uuid: str
    timestamp: datetime
    line_num: int
    is_sidechain: bool


def _user_content_factory() -> list[TextBlockDict | ToolResultBlockDict]:
    return []


def _assistant_content_factory() -> list[TextBlockDict | ThinkingBlockDict | ToolUseBlockDict]:
    return []


@dataclass
class UserSessionMessage(BaseSessionMessage):
    """User message from a Claude Code session (text or tool results)."""

    content: list[TextBlockDict | ToolResultBlockDict] = field(default_factory=_user_content_factory)

    @property
    def text_content(self) -> str:
        return "\n".join(b["text"] for b in self.content if b["type"] == "text")

    @property
    def tool_results(self) -> list[ToolResultBlockDict]:
        return [b for b in self.content if b["type"] == "tool_result"]


@dataclass
class AssistantSessionMessage(BaseSessionMessage):
    """Assistant message from a Claude Code session (text, thinking, and/or tool calls)."""

    content: list[TextBlockDict | ThinkingBlockDict | ToolUseBlockDict] = field(
        default_factory=_assistant_content_factory
    )
    model: str | None = None
    usage: dict[str, Any] | None = None

    @property
    def text_content(self) -> str:
        return "\n".join(b["text"] for b in self.content if b["type"] == "text")

    @property
    def tool_calls(self) -> list[ToolUseBlockDict]:
        return [b for b in self.content if b["type"] == "tool_use"]


@dataclass
class MetaSessionMessage(BaseSessionMessage):
    """Special-case user message (compact summary or skill content) stored as a direct string."""

    meta_type: MetaMessageType = MetaMessageType.COMPACT_SUMMARY
    text_content: str = ""


@dataclass
class LocalCommandSessionMessage(BaseSessionMessage):
    """Local command executed during a Claude Code session (shell or slash command)."""

    command_type: LocalCommandType = LocalCommandType.SHELL
    command: str = ""
    output: str = ""
    is_error: bool = False


# Union type for all parsed session message variants
SessionMessage = UserSessionMessage | AssistantSessionMessage | MetaSessionMessage | LocalCommandSessionMessage
