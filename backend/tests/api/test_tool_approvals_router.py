"""Tests for tool approvals API router."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.engines.claude_code.tool_approval_manager import (
    ToolApprovalRequest,
)
from devboard.api.routers.tool_approvals import (
    ToolApprovalDecisionSchema,
    cancel_conversation_approvals,
    get_approval_stats,
    get_pending_approvals,
    respond_to_approval,
)


@pytest.mark.asyncio
class TestToolApprovalsRouterEndpoints:
    """Test suite for tool approvals API endpoint functions."""

    async def test_get_pending_approvals_endpoint(self):
        """Test get_pending_approvals endpoint function."""
        # Mock the approval manager
        mock_manager = AsyncMock()
        mock_manager.get_pending_approvals.return_value = [
            ToolApprovalRequest(
                request_id="test-123",
                conversation_id=1,
                tool_name="Read",
                tool_args={"file_path": "/test.txt"},
                timestamp=datetime.now(UTC),
            )
        ]

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            result = await get_pending_approvals(conversation_id=1)

        assert len(result) == 1
        assert result[0].request_id == "test-123"
        assert result[0].conversation_id == 1
        assert result[0].tool_name == "Read"
        mock_manager.get_pending_approvals.assert_called_once_with(conversation_id=1)

    async def test_get_pending_approvals_no_filter(self):
        """Test get_pending_approvals without conversation filter."""
        mock_manager = AsyncMock()
        mock_manager.get_pending_approvals.return_value = []

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            result = await get_pending_approvals(conversation_id=None)

        assert result == []
        mock_manager.get_pending_approvals.assert_called_once_with(conversation_id=None)

    async def test_respond_to_approval_endpoint_success(self):
        """Test respond_to_approval endpoint when request exists."""
        mock_manager = AsyncMock()
        mock_manager.respond_to_approval.return_value = True

        decision = ToolApprovalDecisionSchema(approved=True)

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            result = await respond_to_approval("test-123", decision)

        assert result["approved"] is True
        assert result["request_id"] == "test-123"
        mock_manager.respond_to_approval.assert_called_once()
        call_args = mock_manager.respond_to_approval.call_args
        assert call_args[0][0] == "test-123"
        assert call_args[0][1].approved is True

    async def test_respond_to_approval_endpoint_not_found(self):
        """Test respond_to_approval endpoint when request doesn't exist."""
        mock_manager = AsyncMock()
        mock_manager.respond_to_approval.return_value = False

        decision = ToolApprovalDecisionSchema(approved=True)

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            with pytest.raises(Exception) as exc_info:
                await respond_to_approval("nonexistent", decision)

        assert "not found" in str(exc_info.value).lower()

    async def test_respond_to_approval_with_feedback(self):
        """Test respond_to_approval with denial and feedback."""
        mock_manager = AsyncMock()
        mock_manager.respond_to_approval.return_value = True

        decision = ToolApprovalDecisionSchema(
            approved=False,
            feedback="Too dangerous",
        )

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            result = await respond_to_approval("test-456", decision)

        assert result["approved"] is False
        call_args = mock_manager.respond_to_approval.call_args
        assert call_args[0][1].approved is False
        assert call_args[0][1].feedback == "Too dangerous"

    async def test_respond_to_approval_with_modified_args(self):
        """Test respond_to_approval with modified arguments."""
        mock_manager = AsyncMock()
        mock_manager.respond_to_approval.return_value = True

        decision = ToolApprovalDecisionSchema(
            approved=True,
            modified_args={"file_path": "/safe.txt"},
        )

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            await respond_to_approval("test-789", decision)

        call_args = mock_manager.respond_to_approval.call_args
        assert call_args[0][1].modified_args == {"file_path": "/safe.txt"}

    async def test_cancel_conversation_approvals_endpoint(self):
        """Test cancel_conversation_approvals endpoint."""
        mock_manager = AsyncMock()
        mock_manager.cancel_pending_approvals.return_value = 3

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            result = await cancel_conversation_approvals(conversation_id=1)

        assert result["cancelled_count"] == 3
        assert result["conversation_id"] == 1
        mock_manager.cancel_pending_approvals.assert_called_once_with(1)

    async def test_get_approval_stats_endpoint(self):
        """Test get_approval_stats endpoint."""
        mock_manager = Mock()  # Use Mock instead of AsyncMock since get_stats is sync
        mock_manager.get_stats.return_value = {
            "pending_count": 5,
            "max_pending": 100,
            "default_timeout": 300.0,
        }

        with patch("devboard.api.routers.tool_approvals.get_approval_manager", return_value=mock_manager):
            result = await get_approval_stats()

        assert result.pending_count == 5
        assert result.max_pending == 100
        assert result.default_timeout == 300.0
        mock_manager.get_stats.assert_called_once()
