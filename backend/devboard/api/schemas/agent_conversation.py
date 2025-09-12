"""Shared schemas for agent conversation endpoints with deferred tools support."""

import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class MessageRole(StrEnum):
    USER = "user"
    AGENT = "agent"


class ConversationMessage(BaseModel):
    """Model for an agent conversation message (only contains final response for agent)."""

    id: int
    role: MessageRole
    text_content: str
    timestamp: datetime.datetime


class ToolCallRequest(BaseModel):
    """Tool call requiring user approval."""

    tool_call_id: str
    tool_name: str
    tool_args: str | dict[str, Any] | None = None


class PromptResponseType(StrEnum):
    MESSAGE = "message"
    TOOL_REQUEST = "tool_request"


class PromptResponse(BaseModel):
    """
    Response after processing a user message or tool approval(s).
    Will contain either the agent final response, or pending tool request(s).
    """

    type: PromptResponseType
    message: ConversationMessage | None = None
    tool_requests: list[ToolCallRequest] | None = None


class UserPrompt(BaseModel):
    """Request to send a message to an agent."""

    message: str


class ToolApprovalDecision(BaseModel):
    """User decision on a single tool call."""

    approved: bool
    feedback: str | None = None  # For denials with feedback


class ToolApprovalRequest(BaseModel):
    """Request to approve or deny tool calls."""

    approvals: dict[str, ToolApprovalDecision]  # tool_call_id -> decision
