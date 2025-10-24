"""Shared schemas for agent conversation endpoints with deferred tools support."""

from enum import StrEnum

from pydantic import BaseModel

from devboard.agents.events import ConversationMessage, ToolCallRequest


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


class ToolApprovals(BaseModel):
    """Request to approve or deny tool calls."""

    # TODO: Make a type for dict[str, ToolApprovalDecision] and use it isntead, rename this ToolApprovals to ToolApprovalsRequest
    approvals: dict[str, ToolApprovalDecision]  # tool_call_id -> decision


class ChatRequest(BaseModel):
    """Request model for project or task chat."""

    message: str
