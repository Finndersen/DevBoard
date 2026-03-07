"""Session message dataclasses for Claude Code sessions."""

from dataclasses import dataclass, field
from datetime import datetime

from devboard.agents.engines.claude_code.session.types import TextBlockDict, ToolResultBlockDict, ToolUseBlockDict
from devboard.agents.events import MetaMessageType


@dataclass
class BaseSessionMessage:
    """Common fields for all session message types."""

    uuid: str
    timestamp: datetime
    line_num: int
    is_sidechain: bool


@dataclass
class UserSessionMessage(BaseSessionMessage):
    """User message from a Claude Code session (text or tool results)."""

    content: list[TextBlockDict | ToolResultBlockDict] = field(default_factory=list)

    @property
    def text_content(self) -> str:
        return "\n".join(b["text"] for b in self.content if b["type"] == "text")

    @property
    def tool_results(self) -> list[ToolResultBlockDict]:
        return [b for b in self.content if b["type"] == "tool_result"]


@dataclass
class AssistantSessionMessage(BaseSessionMessage):
    """Assistant message from a Claude Code session (text and/or tool calls)."""

    content: list[TextBlockDict | ToolUseBlockDict] = field(default_factory=list)

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


# Union type for all parsed session message variants
SessionMessage = UserSessionMessage | AssistantSessionMessage | MetaSessionMessage
