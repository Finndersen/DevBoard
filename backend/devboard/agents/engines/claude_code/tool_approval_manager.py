"""In-memory tool approval manager for Claude Code agent tool execution.

This service enables human-in-the-loop tool approval for Claude Code agents by managing
approval requests using async queues.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import logfire


@dataclass
class ToolApprovalRequest:
    """Represents a tool approval request waiting for user decision.

    Attributes:
        request_id: Unique identifier for this approval request
        conversation_id: ID of conversation this approval belongs to
        tool_name: Name of the tool requesting approval
        tool_args: Arguments the tool will be called with
        timestamp: When the request was created
    """

    request_id: str
    conversation_id: int
    tool_name: str
    tool_args: dict[str, Any]
    timestamp: datetime


@dataclass
class ToolApprovalResponse:
    """Response to a tool approval request.

    Attributes:
        approved: Whether the tool execution was approved
        feedback: Optional feedback message (used when denying)
        modified_args: Optional modified arguments (for approved tools)
    """

    approved: bool
    feedback: str | None = None
    modified_args: dict[str, Any] | None = None


class ToolApprovalManager:
    """Manages in-memory tool approval requests using async queues.

    This manager enables pausing agent execution until user approval is received.
    It uses asyncio.Queue to block waiting tasks and signal them when decisions
    are made.

    Thread-safe for concurrent approval requests and responses.
    """

    def __init__(self, default_timeout: float = 300.0, max_pending: int = 100):
        """Initialize the approval manager.

        Args:
            default_timeout: Default timeout in seconds for approval requests
            max_pending: Maximum number of pending approvals allowed
        """
        self._pending: dict[str, tuple[ToolApprovalRequest, asyncio.Queue[ToolApprovalResponse]]] = {}
        self._lock = asyncio.Lock()
        self._default_timeout = default_timeout
        self._max_pending = max_pending

    async def request_approval(
        self,
        conversation_id: int,
        tool_name: str,
        tool_args: dict[str, Any],
        timeout: float | None = None,
    ) -> ToolApprovalResponse:
        """Request approval for a tool execution and block until response.

        This method creates a pending approval request and blocks the calling
        task until a response is provided via respond_to_approval() or the
        timeout expires.

        Args:
            conversation_id: ID of the conversation this tool call belongs to
            tool_name: Name of the tool requesting approval
            tool_args: Arguments the tool will be called with
            timeout: Optional timeout in seconds (uses default if None)

        Returns:
            ToolApprovalResponse with user's decision

        Raises:
            asyncio.TimeoutError: If timeout expires before response received
            RuntimeError: If max pending approvals limit exceeded
        """
        async with self._lock:
            if len(self._pending) >= self._max_pending:
                raise RuntimeError(
                    f"Maximum pending approvals ({self._max_pending}) exceeded. "
                    "Respond to existing approvals before creating new ones."
                )

            request_id = str(uuid4())
            request = ToolApprovalRequest(
                request_id=request_id,
                conversation_id=conversation_id,
                tool_name=tool_name,
                tool_args=tool_args,
                timestamp=datetime.now(UTC),
            )
            response_queue: asyncio.Queue[ToolApprovalResponse] = asyncio.Queue(maxsize=1)
            self._pending[request_id] = (request, response_queue)

        logfire.info(
            f"Tool approval requested: {request_id} (conversation={conversation_id}, "
            f"tool={tool_name}, pending={len(self._pending)})"
        )

        # Block until response received or timeout
        timeout_seconds = timeout if timeout is not None else self._default_timeout
        try:
            response = await asyncio.wait_for(response_queue.get(), timeout=timeout_seconds)
            logfire.info(
                f"Tool approval received: {request_id} (approved={response.approved}, feedback={response.feedback})"
            )
            return response
        except TimeoutError:
            logfire.warning(f"Tool approval timeout: {request_id} (timeout={timeout_seconds}s)")
            # Return denied response on timeout
            return ToolApprovalResponse(
                approved=False,
                feedback="Approval request timed out - no response received from user",
            )
        finally:
            # Always cleanup
            async with self._lock:
                self._pending.pop(request_id, None)

    async def respond_to_approval(
        self,
        request_id: str,
        response: ToolApprovalResponse,
    ) -> bool:
        """Respond to a pending approval request.

        This method sends the approval decision to the waiting task, unblocking
        the agent execution.

        Args:
            request_id: ID of the approval request to respond to
            response: The approval decision and optional feedback/modifications

        Returns:
            True if response was delivered, False if request not found

        Raises:
            RuntimeError: If queue is somehow full (should never happen)
        """
        async with self._lock:
            pending = self._pending.get(request_id)
            if not pending:
                logfire.warning(f"Approval response for unknown request: {request_id}")
                return False

            request, response_queue = pending

        try:
            # Put response in queue (maxsize=1, so should never block)
            await asyncio.wait_for(response_queue.put(response), timeout=1.0)
            logfire.info(
                f"Approval response delivered: {request_id} "
                f"(conversation={request.conversation_id}, approved={response.approved})"
            )
            return True
        except TimeoutError as e:
            # This should never happen since maxsize=1 and we only put once
            logfire.error(f"Failed to deliver approval response: {request_id} (queue full?)")
            raise RuntimeError(f"Failed to deliver approval response for {request_id}") from e

    async def get_pending_approvals(
        self,
        conversation_id: int | None = None,
    ) -> list[ToolApprovalRequest]:
        """Get list of pending approval requests.

        Args:
            conversation_id: Optional filter by conversation ID

        Returns:
            List of pending ToolApprovalRequest objects
        """
        async with self._lock:
            requests = [req for req, _ in self._pending.values()]

            if conversation_id is not None:
                requests = [req for req in requests if req.conversation_id == conversation_id]

            # Sort by timestamp (oldest first)
            requests.sort(key=lambda r: r.timestamp)
            return requests

    async def cancel_pending_approvals(self, conversation_id: int) -> int:
        """Cancel all pending approvals for a conversation.

        Useful when a conversation is deleted or agent execution is stopped.

        Args:
            conversation_id: ID of conversation to cancel approvals for

        Returns:
            Number of approvals cancelled
        """
        async with self._lock:
            to_cancel = [
                request_id
                for request_id, (request, _) in self._pending.items()
                if request.conversation_id == conversation_id
            ]

            for request_id in to_cancel:
                _, queue = self._pending.pop(request_id)
                # Send denial response to unblock any waiting tasks
                try:
                    await asyncio.wait_for(
                        queue.put(
                            ToolApprovalResponse(
                                approved=False,
                                feedback="Approval cancelled due to conversation closure",
                            )
                        ),
                        timeout=1.0,
                    )
                except TimeoutError:
                    logfire.error(f"Failed to cancel approval: {request_id}")

            logfire.info(f"Cancelled {len(to_cancel)} pending approvals for conversation {conversation_id}")
            return len(to_cancel)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about pending approvals.

        Returns:
            Dictionary with statistics
        """
        return {
            "pending_count": len(self._pending),
            "max_pending": self._max_pending,
            "default_timeout": self._default_timeout,
        }


# Global singleton instance
_approval_manager: ToolApprovalManager | None = None


def get_approval_manager() -> ToolApprovalManager:
    """Get or create the global approval manager instance.

    Returns:
        Global ToolApprovalManager singleton
    """
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ToolApprovalManager()
    return _approval_manager
