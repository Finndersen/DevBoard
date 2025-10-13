"""API router for tool approval requests and responses."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from devboard.agents.engines.claude_code.tool_approval_manager import ToolApprovalResponse, get_approval_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tool-approvals", tags=["tool-approvals"])


# Request/Response Models


class ToolApprovalRequestSchema(BaseModel):
    """Schema for a tool approval request."""

    request_id: str = Field(description="Unique identifier for this approval request")
    conversation_id: int = Field(description="ID of conversation this approval belongs to")
    tool_name: str = Field(description="Name of the tool requesting approval")
    tool_args: dict = Field(description="Arguments the tool will be called with")
    timestamp: str = Field(description="ISO 8601 timestamp when request was created")


class ToolApprovalDecisionSchema(BaseModel):
    """Schema for user's approval decision."""

    approved: bool = Field(description="Whether to approve tool execution")
    feedback: str | None = Field(default=None, description="Optional feedback message (used when denying)")
    modified_args: dict | None = Field(default=None, description="Optional modified arguments (for approved tools)")


class ToolApprovalStatsSchema(BaseModel):
    """Schema for approval manager statistics."""

    pending_count: int = Field(description="Number of pending approvals")
    max_pending: int = Field(description="Maximum allowed pending approvals")
    default_timeout: float = Field(description="Default timeout in seconds")


# API Endpoints


@router.get(
    "/pending",
    response_model=list[ToolApprovalRequestSchema],
    summary="Get pending tool approval requests",
)
async def get_pending_approvals(
    conversation_id: Annotated[int | None, Query(description="Filter by conversation ID")] = None,
) -> list[ToolApprovalRequestSchema]:
    """Get list of pending tool approval requests.

    Args:
        conversation_id: Optional filter by conversation ID

    Returns:
        List of pending approval requests
    """
    approval_manager = get_approval_manager()
    pending = await approval_manager.get_pending_approvals(conversation_id=conversation_id)

    return [
        ToolApprovalRequestSchema(
            request_id=req.request_id,
            conversation_id=req.conversation_id,
            tool_name=req.tool_name,
            tool_args=req.tool_args,
            timestamp=req.timestamp.isoformat(),
        )
        for req in pending
    ]


@router.post(
    "/{request_id}/respond",
    status_code=200,
    summary="Respond to a tool approval request",
)
async def respond_to_approval(
    request_id: Annotated[str, Path(description="ID of the approval request")],
    decision: ToolApprovalDecisionSchema,
) -> dict:
    """Respond to a pending tool approval request.

    This endpoint unblocks the agent waiting for approval and continues
    execution with the provided decision.

    Args:
        request_id: ID of the approval request to respond to
        decision: User's approval decision

    Returns:
        Success message

    Raises:
        HTTPException: If request_id not found (404)
    """
    approval_manager = get_approval_manager()

    response = ToolApprovalResponse(
        approved=decision.approved,
        feedback=decision.feedback,
        modified_args=decision.modified_args,
    )

    success = await approval_manager.respond_to_approval(request_id, response)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request '{request_id}' not found or already responded to",
        )

    logger.info(
        f"Approval response recorded: {request_id} (approved={decision.approved}, feedback={decision.feedback})"
    )

    return {
        "message": "Approval response recorded successfully",
        "request_id": request_id,
        "approved": decision.approved,
    }


@router.delete(
    "/conversation/{conversation_id}",
    status_code=200,
    summary="Cancel all pending approvals for a conversation",
)
async def cancel_conversation_approvals(
    conversation_id: Annotated[int, Path(description="ID of the conversation")],
) -> dict:
    """Cancel all pending approvals for a conversation.

    Useful when a conversation is deleted or agent execution is stopped.
    All pending approvals are denied with cancellation message.

    Args:
        conversation_id: ID of conversation to cancel approvals for

    Returns:
        Number of approvals cancelled
    """
    approval_manager = get_approval_manager()
    cancelled_count = await approval_manager.cancel_pending_approvals(conversation_id)

    logger.info(f"Cancelled {cancelled_count} approvals for conversation {conversation_id}")

    return {
        "message": f"Cancelled {cancelled_count} pending approval(s)",
        "conversation_id": conversation_id,
        "cancelled_count": cancelled_count,
    }


@router.get(
    "/stats",
    response_model=ToolApprovalStatsSchema,
    summary="Get approval manager statistics",
)
async def get_approval_stats() -> ToolApprovalStatsSchema:
    """Get statistics about the approval manager.

    Returns:
        Statistics including pending count, max pending, and default timeout
    """
    approval_manager = get_approval_manager()
    stats = approval_manager.get_stats()

    return ToolApprovalStatsSchema(**stats)
