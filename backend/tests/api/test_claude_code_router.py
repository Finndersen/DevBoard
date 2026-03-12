"""Tests for Claude Code session viewer API endpoints."""

from unittest.mock import patch

from devboard.agents.events import MessageRole, TextMessage


class TestSubAgentMessagesEndpoint:
    """Tests for GET /api/claude-code/sessions/{session_id}/subagents/{agent_id}/messages."""

    def test_returns_sub_agent_messages(self, client):
        """Should return parsed conversation events for a valid sub-agent."""
        mock_events = [
            TextMessage(
                role=MessageRole.USER,
                text_content="Hello sub-agent",
                timestamp="2025-01-01T00:00:00Z",
                uuid="test-uuid-1",
            ),
            TextMessage(
                role=MessageRole.AGENT,
                text_content="Hi, I'm the sub-agent",
                timestamp="2025-01-01T00:00:01Z",
                uuid="test-uuid-2",
            ),
        ]

        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.get_sub_agent_messages",
            return_value=mock_events,
        ) as mock_method:
            response = client.get("/api/claude-code/sessions/parent-123/subagents/abc1234/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["event_type"] == "message"
        assert data[0]["text_content"] == "Hello sub-agent"
        assert data[1]["text_content"] == "Hi, I'm the sub-agent"
        mock_method.assert_called_once_with("parent-123", "abc1234")

    def test_returns_404_when_file_not_found(self, client):
        """Should return 404 when sub-agent file doesn't exist."""
        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.get_sub_agent_messages",
            side_effect=FileNotFoundError("Sub-agent session file not found"),
        ):
            response = client.get("/api/claude-code/sessions/parent-123/subagents/nonexistent/messages")

        assert response.status_code == 404
        assert "Sub-agent session file not found" in response.json()["detail"]

    def test_returns_400_for_invalid_agent_id(self, client):
        """Should return 400 when agent_id contains invalid characters."""
        with patch(
            "devboard.api.routers.claude_code.ClaudeSessionManager.get_sub_agent_messages",
            side_effect=ValueError("Invalid agent_id: agent.bad"),
        ):
            response = client.get("/api/claude-code/sessions/parent-123/subagents/agent.bad/messages")

        assert response.status_code == 400
        assert "Invalid agent_id" in response.json()["detail"]
