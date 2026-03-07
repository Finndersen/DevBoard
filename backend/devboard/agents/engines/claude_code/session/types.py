"""TypedDict schema definitions for Claude Code session JSONL files."""

from typing import Any, Literal, NotRequired, TypedDict


class CacheCreationDict(TypedDict):
    """Cache creation statistics in usage data."""

    ephemeral_5m_input_tokens: int
    ephemeral_1h_input_tokens: int


class UsageDict(TypedDict):
    """Token usage statistics in API response.

    Core fields (input_tokens, output_tokens) are always present.
    Caching-related fields are present when prompt caching is used.
    """

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: NotRequired[int]
    cache_read_input_tokens: NotRequired[int]
    cache_creation: NotRequired[CacheCreationDict]
    service_tier: NotRequired[str]


class TextBlockDict(TypedDict):
    """Text content block in a message."""

    type: Literal["text"]
    text: str


class ToolUseBlockDict(TypedDict):
    """Tool use content block in assistant messages."""

    type: Literal["tool_use"]
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlockDict(TypedDict):
    """Tool result content block in user messages."""

    type: Literal["tool_result"]
    tool_use_id: str
    content: str | list[dict[str, Any]]
    is_error: NotRequired[bool]  # Optional - defaults to False


# Union type for all content block types
MessageContentDict = TextBlockDict | ToolUseBlockDict | ToolResultBlockDict


class UserMessageDict(TypedDict):
    """User message data structure."""

    role: str  # "user"
    content: str | list[TextBlockDict] | list[ToolResultBlockDict]


class AssistantMessageDict(TypedDict):
    """Assistant message data structure (API response)."""

    role: str  # "assistant"
    content: list[TextBlockDict | ToolUseBlockDict]
    model: str
    id: str
    type: str
    stop_reason: str | None
    stop_sequence: str | None
    usage: UsageDict


class ToolUseResultDict(TypedDict):
    """Tool execution result metadata."""

    stdout: str
    stderr: str
    interrupted: bool
    isImage: bool


class SummaryEntry(TypedDict):
    """Summary entry in JSONL file."""

    type: str  # "summary"
    summary: str
    leafUuid: str


class BaseMessageEntry(TypedDict):
    """Base fields common to both user and assistant message entries."""

    type: str  # "user" or "assistant"
    uuid: str
    timestamp: str  # ISO format datetime
    parentUuid: str | None
    isSidechain: bool
    userType: str
    cwd: str
    sessionId: str
    version: str
    gitBranch: str


class UserEntry(BaseMessageEntry):
    """User message entry in JSONL file."""

    type: str  # "user"
    message: UserMessageDict
    toolUseResult: NotRequired[ToolUseResultDict]
    isCompactSummary: NotRequired[bool]
    isMeta: NotRequired[bool]


class AssistantEntry(BaseMessageEntry):
    """Assistant message entry in JSONL file."""

    type: str  # "assistant"
    message: AssistantMessageDict
    requestId: str


# Union type for message entries (user/assistant only)
MessageEntry = UserEntry | AssistantEntry

# Union type for all JSONL entry types (includes non-message entries like summaries)
JSONLEntry = SummaryEntry | MessageEntry
