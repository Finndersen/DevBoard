"""Shared schemas for agent conversation endpoints with deferred tools support."""

import datetime
from typing import Any

from pydantic import BaseModel

from .task import DocumentEdit


class ConversationMessageResponse(BaseModel):
    """Simplified message response for frontend display."""

    id: int
    message_type: str  # 'request' or 'response'
    text_content: str | None  # Extracted from pydantic_content for display
    tool_calls: list["ToolCallInfo"] | None  # Extracted tool call information
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ToolCallInfo(BaseModel):
    """Information about a tool call for frontend display."""

    tool_call_id: str
    tool_name: str
    status: str  # 'pending_approval', 'approved', 'denied'
    arguments: dict[str, Any]  # Tool call arguments
    preview: dict[str, Any] | None = None  # For document edits, include diff preview


class PendingApproval(BaseModel):
    """Tool call requiring user approval."""

    tool_call_id: str
    tool_name: str
    document_type: str | None = None
    edits: list[DocumentEdit] | None = None
    diff_preview: str | None = None  # Generated diff for UI display
    reasoning: str | None = None


class ConversationResponse(BaseModel):
    """Response after processing a message or tool approval."""

    messages: list[ConversationMessageResponse]
    pending_approvals: list[PendingApproval] | None = None
    conversation_complete: bool = True  # False if waiting for tool approvals


class MessageRequest(BaseModel):
    """Request to send a message to an agent."""

    message: str


class ToolApprovalDecision(BaseModel):
    """User decision on a single tool call."""

    approved: bool
    feedback: str | None = None  # For denials with feedback


class ToolApprovalRequest(BaseModel):
    """Request to approve or deny tool calls."""

    approvals: dict[str, ToolApprovalDecision]  # tool_call_id -> decision
