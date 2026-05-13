"""Tests for Claude Code session viewer API endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.events import MessageRole, TextMessage
from devboard.api.routers.claude_code import _parse_mcp_servers
from devboard.api.schemas.claude_code import McpServerStatus, McpServerType


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


class TestParseMcpServers:
    """Tests for _parse_mcp_servers parsing function."""

    def test_parses_simple_name_with_remote_url(self):
        """Should parse simple name with remote URL."""
        output = "claude.ai Atlassian: https://mcp.atlassian.com/v1/mcp - ✓ Connected"
        servers = _parse_mcp_servers(output)

        assert len(servers) == 1
        assert servers[0].name == "claude.ai Atlassian"
        assert servers[0].url_or_command == "https://mcp.atlassian.com/v1/mcp"
        assert servers[0].status == McpServerStatus.connected
        assert servers[0].type == McpServerType.remote

    def test_parses_plugin_style_name(self):
        """Should parse plugin-style name with local command."""
        output = "plugin:my-plugin:local-server: /usr/local/bin/my-mcp-server --flag - ✗ Failed to connect"
        servers = _parse_mcp_servers(output)

        assert len(servers) == 1
        assert servers[0].name == "plugin:my-plugin:local-server"
        assert servers[0].url_or_command == "/usr/local/bin/my-mcp-server --flag"
        assert servers[0].status == McpServerStatus.failed
        assert servers[0].type == McpServerType.local

    def test_parses_needs_authentication_status(self):
        """Should parse needs_auth status."""
        output = "claude.ai Slack: https://mcp.slack.com/mcp - ! Needs authentication"
        servers = _parse_mcp_servers(output)

        assert len(servers) == 1
        assert servers[0].status == McpServerStatus.needs_auth

    def test_parses_multiple_servers(self):
        """Should parse multiple servers from output."""
        output = """claude.ai Atlassian: https://mcp.atlassian.com/v1/mcp - ✓ Connected
claude.ai Slack: https://mcp.slack.com/mcp - ! Needs authentication
plugin:my-plugin:local-server: /usr/local/bin/my-mcp-server --flag - ✗ Failed to connect"""
        servers = _parse_mcp_servers(output)

        assert len(servers) == 3
        assert servers[0].name == "claude.ai Atlassian"
        assert servers[1].name == "claude.ai Slack"
        assert servers[2].name == "plugin:my-plugin:local-server"

    def test_handles_command_with_dashes(self):
        """Should correctly split on last ' - ' when command contains dashes."""
        output = "test-server: /path/to/my-command -arg1 -arg2 - ✓ Connected"
        servers = _parse_mcp_servers(output)

        assert len(servers) == 1
        assert servers[0].url_or_command == "/path/to/my-command -arg1 -arg2"
        assert servers[0].status == McpServerStatus.connected

    def test_skips_malformed_lines(self):
        """Should skip lines that don't match expected format."""
        output = """claude.ai Atlassian: https://mcp.atlassian.com/v1/mcp - ✓ Connected
invalid line without colon
another-invalid: missing-dash-separator
valid-server: http://example.com - ✓ Connected"""
        servers = _parse_mcp_servers(output)

        assert len(servers) == 2
        assert servers[0].name == "claude.ai Atlassian"
        assert servers[1].name == "valid-server"

    def test_skips_empty_lines(self):
        """Should skip empty lines."""
        output = """claude.ai Atlassian: https://mcp.atlassian.com/v1/mcp - ✓ Connected

valid-server: http://example.com - ✓ Connected"""
        servers = _parse_mcp_servers(output)

        assert len(servers) == 2

    def test_detects_http_urls_as_remote(self):
        """Should detect http URLs as remote type."""
        output = "test-server: http://example.com - ✓ Connected"
        servers = _parse_mcp_servers(output)

        assert servers[0].type == McpServerType.remote

    def test_detects_paths_as_local(self):
        """Should detect file paths as local type."""
        output = "test-server: /usr/bin/my-server - ✓ Connected"
        servers = _parse_mcp_servers(output)

        assert servers[0].type == McpServerType.local

    def test_handles_empty_output(self):
        """Should return empty list for empty output."""
        servers = _parse_mcp_servers("")
        assert servers == []

    def test_handles_output_with_only_whitespace(self):
        """Should return empty list for output with only whitespace."""
        servers = _parse_mcp_servers("   \n\n   ")
        assert servers == []


class TestMcpServersEndpoint:
    """Tests for GET /api/claude-code/mcp-servers endpoint."""

    @pytest.mark.asyncio
    async def test_returns_mcp_servers(self, client):
        """Should return parsed MCP servers from cli command."""
        mock_output = """claude.ai Atlassian: https://mcp.atlassian.com/v1/mcp - ✓ Connected
claude.ai Slack: https://mcp.slack.com/mcp - ! Needs authentication
plugin:my-plugin:local-server: /usr/local/bin/my-mcp-server --flag - ✗ Failed to connect"""

        mock_result = Mock()
        mock_result.success = True
        mock_result.stdout = mock_output
        mock_result.stderr = ""

        with patch(
            "devboard.api.routers.claude_code.execute_shell_command",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_exec:
            response = client.get("/api/claude-code/mcp-servers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["name"] == "claude.ai Atlassian"
        assert data[0]["type"] == "remote"
        assert data[0]["status"] == "connected"
        assert data[1]["status"] == "needs_auth"
        assert data[2]["status"] == "failed"
        assert data[2]["type"] == "local"
        mock_exec.assert_called_once_with(["claude", "mcp", "list"], raise_on_error=False)

    @pytest.mark.asyncio
    async def test_returns_502_when_command_fails(self, client):
        """Should return 502 when claude mcp list command fails."""
        mock_result = Mock()
        mock_result.success = False
        mock_result.stderr = "claude: command not found"

        with patch(
            "devboard.api.routers.claude_code.execute_shell_command",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = client.get("/api/claude-code/mcp-servers")

        assert response.status_code == 502
        assert "Failed to list MCP servers" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_502_when_shell_command_raises(self, client):
        """Should return 502 when shell command raises exception."""
        from devboard.integrations.shell import ShellCommandError

        with patch(
            "devboard.api.routers.claude_code.execute_shell_command",
            new_callable=AsyncMock,
            side_effect=ShellCommandError("Command execution failed"),
        ):
            response = client.get("/api/claude-code/mcp-servers")

        assert response.status_code == 502
        assert "Failed to list MCP servers" in response.json()["detail"]
