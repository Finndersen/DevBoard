"""Tests for ToolApprovalManager service."""

import asyncio

import pytest

from devboard.agents.claude_code.tool_approval_manager import (
    ToolApprovalManager,
    ToolApprovalResponse,
    get_approval_manager,
)


@pytest.fixture
def approval_manager():
    """Create a fresh ToolApprovalManager for each test."""
    return ToolApprovalManager(default_timeout=1.0, max_pending=5)


@pytest.mark.asyncio
class TestToolApprovalManager:
    """Test suite for ToolApprovalManager."""

    async def test_basic_approval_flow(self, approval_manager):
        """Test basic approve flow: request → approve → returns approved."""

        async def request_task():
            response = await approval_manager.request_approval(
                conversation_id=1,
                tool_name="Read",
                tool_args={"file_path": "/test.txt"},
            )
            return response

        async def respond_task():
            # Wait a bit to ensure request is pending
            await asyncio.sleep(0.1)

            # Get pending approvals
            pending = await approval_manager.get_pending_approvals()
            assert len(pending) == 1
            request = pending[0]

            # Approve it
            success = await approval_manager.respond_to_approval(
                request.request_id,
                ToolApprovalResponse(approved=True),
            )
            assert success is True

        # Run request and response concurrently
        response = await asyncio.gather(request_task(), respond_task())

        # Check the response
        approval_response = response[0]
        assert approval_response.approved is True
        assert approval_response.feedback is None

    async def test_denial_flow(self, approval_manager):
        """Test denial flow: request → deny → returns denied."""

        async def request_task():
            response = await approval_manager.request_approval(
                conversation_id=1,
                tool_name="Write",
                tool_args={"file_path": "/test.txt", "content": "test"},
            )
            return response

        async def respond_task():
            await asyncio.sleep(0.1)
            pending = await approval_manager.get_pending_approvals()
            request = pending[0]

            success = await approval_manager.respond_to_approval(
                request.request_id,
                ToolApprovalResponse(approved=False, feedback="Not allowed"),
            )
            assert success is True

        response = await asyncio.gather(request_task(), respond_task())
        approval_response = response[0]

        assert approval_response.approved is False
        assert approval_response.feedback == "Not allowed"

    async def test_timeout(self, approval_manager):
        """Test timeout: request → no response → times out."""
        response = await approval_manager.request_approval(
            conversation_id=1,
            tool_name="Bash",
            tool_args={"command": "ls"},
            timeout=0.5,
        )

        # Should auto-deny on timeout
        assert response.approved is False
        assert "timed out" in response.feedback.lower()

    async def test_concurrent_approvals(self, approval_manager):
        """Test concurrent approvals: multiple independent requests."""

        async def request_task(conv_id, tool_name):
            response = await approval_manager.request_approval(
                conversation_id=conv_id,
                tool_name=tool_name,
                tool_args={},
            )
            return response

        async def respond_all_task():
            await asyncio.sleep(0.1)

            # Get all pending
            pending = await approval_manager.get_pending_approvals()
            assert len(pending) == 3

            # Approve all
            for request in pending:
                await approval_manager.respond_to_approval(
                    request.request_id,
                    ToolApprovalResponse(approved=True),
                )

        # Start 3 concurrent requests
        responses = await asyncio.gather(
            request_task(1, "Read"),
            request_task(2, "Write"),
            request_task(3, "Bash"),
            respond_all_task(),
        )

        # Check all approved
        assert responses[0].approved is True
        assert responses[1].approved is True
        assert responses[2].approved is True

    async def test_request_not_found(self, approval_manager):
        """Test respond to non-existent ID → returns False."""
        success = await approval_manager.respond_to_approval(
            "non-existent-id",
            ToolApprovalResponse(approved=True),
        )
        assert success is False

    async def test_cleanup_after_completion(self, approval_manager):
        """Test cleanup: after completion → removed from pending."""

        async def request_task():
            return await approval_manager.request_approval(
                conversation_id=1,
                tool_name="Read",
                tool_args={},
            )

        async def respond_task():
            await asyncio.sleep(0.1)
            pending = await approval_manager.get_pending_approvals()
            request = pending[0]
            await approval_manager.respond_to_approval(
                request.request_id,
                ToolApprovalResponse(approved=True),
            )

        await asyncio.gather(request_task(), respond_task())

        # Check pending is empty
        pending = await approval_manager.get_pending_approvals()
        assert len(pending) == 0

    async def test_cleanup_after_timeout(self, approval_manager):
        """Test cleanup: after timeout → removed from pending."""
        await approval_manager.request_approval(
            conversation_id=1,
            tool_name="Read",
            tool_args={},
            timeout=0.1,
        )

        # Check pending is empty after timeout
        pending = await approval_manager.get_pending_approvals()
        assert len(pending) == 0

    async def test_cancel_pending_approvals(self, approval_manager):
        """Test cancellation: cancel conversation → all pending denied."""

        async def request_task(conv_id):
            return await approval_manager.request_approval(
                conversation_id=conv_id,
                tool_name="Read",
                tool_args={},
                timeout=5.0,  # Longer timeout to prevent race condition
            )

        async def cancel_task():
            await asyncio.sleep(0.2)  # Wait longer for requests to register

            # Cancel conversation 1
            cancelled = await approval_manager.cancel_pending_approvals(1)
            assert cancelled == 2

        # Start 3 requests: 2 for conv 1, 1 for conv 2
        responses = await asyncio.gather(
            request_task(1),
            request_task(1),
            request_task(2),
            cancel_task(),
        )

        # Conv 1 requests should be denied with cancellation message
        assert responses[0].approved is False
        assert "cancelled" in responses[0].feedback.lower()
        assert responses[1].approved is False
        assert "cancelled" in responses[1].feedback.lower()

        # Conv 2 request should have timed out by now (or still pending)
        # Don't check pending since it might have timed out already
        # Just verify the cancellation worked for conv 1

    async def test_max_pending_limit(self, approval_manager):
        """Test max pending limit: exceed limit → raises error."""

        async def request_task(n):
            try:
                await approval_manager.request_approval(
                    conversation_id=n,
                    tool_name="Read",
                    tool_args={},
                    timeout=2.0,
                )
            except RuntimeError as e:
                return str(e)

        # Start 6 requests (max is 5)
        results = await asyncio.gather(
            request_task(1),
            request_task(2),
            request_task(3),
            request_task(4),
            request_task(5),
            request_task(6),
            return_exceptions=True,
        )

        # At least one should fail with max pending error
        errors = [r for r in results if isinstance(r, str) and "Maximum pending" in r]
        assert len(errors) >= 1

    async def test_filter_pending_by_conversation(self, approval_manager):
        """Test filtering pending approvals by conversation ID."""

        async def request_task(conv_id):
            try:
                await approval_manager.request_approval(
                    conversation_id=conv_id,
                    tool_name="Read",
                    tool_args={},
                    timeout=2.0,
                )
            except TimeoutError:
                pass

        async def check_filter_task():
            await asyncio.sleep(0.1)

            # Get all pending
            all_pending = await approval_manager.get_pending_approvals()
            assert len(all_pending) == 3

            # Filter by conversation 1
            conv1_pending = await approval_manager.get_pending_approvals(conversation_id=1)
            assert len(conv1_pending) == 2
            assert all(p.conversation_id == 1 for p in conv1_pending)

            # Filter by conversation 2
            conv2_pending = await approval_manager.get_pending_approvals(conversation_id=2)
            assert len(conv2_pending) == 1
            assert conv2_pending[0].conversation_id == 2

        await asyncio.gather(
            request_task(1),
            request_task(1),
            request_task(2),
            check_filter_task(),
        )

    async def test_modified_args(self, approval_manager):
        """Test approving with modified arguments."""

        async def request_task():
            return await approval_manager.request_approval(
                conversation_id=1,
                tool_name="Write",
                tool_args={"file_path": "/dangerous.txt"},
            )

        async def respond_task():
            await asyncio.sleep(0.1)
            pending = await approval_manager.get_pending_approvals()
            request = pending[0]

            # Approve with modified args
            await approval_manager.respond_to_approval(
                request.request_id,
                ToolApprovalResponse(
                    approved=True,
                    modified_args={"file_path": "/safe.txt"},
                ),
            )

        response = await asyncio.gather(request_task(), respond_task())
        approval_response = response[0]

        assert approval_response.approved is True
        assert approval_response.modified_args == {"file_path": "/safe.txt"}

    async def test_get_stats(self, approval_manager):
        """Test getting approval manager statistics."""
        stats = approval_manager.get_stats()

        assert "pending_count" in stats
        assert "max_pending" in stats
        assert "default_timeout" in stats
        assert stats["max_pending"] == 5
        assert stats["default_timeout"] == 1.0
        assert stats["pending_count"] == 0


def test_get_approval_manager_singleton():
    """Test that get_approval_manager returns a singleton."""
    manager1 = get_approval_manager()
    manager2 = get_approval_manager()

    assert manager1 is manager2
