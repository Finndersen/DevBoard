import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    AGENT = "agent"


class ConversationEventType(StrEnum):
    """Type of event in a conversation stream."""

    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_CALL_REQUEST = "tool_call_request"


class ConversationMessage(BaseModel):
    """Model for a project or task agent conversation message (only contains final response for agent)."""

    event_type: Literal["message"] = "message"
    role: MessageRole
    text_content: str
    timestamp: datetime.datetime


class ToolCall(BaseModel):
    """Represents a tool call made by the agent."""

    event_type: Literal["tool_call"] = "tool_call"
    tool_call_id: str
    tool_name: str
    tool_args: dict[str, Any] | None = None
    timestamp: datetime.datetime


class ToolResult(BaseModel):
    """Result from a tool call execution."""

    event_type: Literal["tool_result"] = "tool_result"
    tool_call_id: str
    result_content: str
    is_error: bool = False
    timestamp: datetime.datetime


class ToolCallRequest(BaseModel):
    """Tool call requiring user approval."""

    event_type: Literal["tool_call_request"] = "tool_call_request"
    tool_call_id: str
    tool_name: str
    tool_args: str | dict[str, Any] | None = None
    timestamp: datetime.datetime


# Union type for all conversation events
type ConversationEvent = Annotated[
    ConversationMessage | ToolCallRequest | ToolCall | ToolResult,
    Field(discriminator="event_type"),
]
