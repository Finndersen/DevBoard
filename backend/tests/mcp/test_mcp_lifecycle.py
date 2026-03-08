"""Tests for MCPLifecycleManager."""

from unittest.mock import Mock, patch

from devboard.db.models.mcp_server import HttpMCPConfig, MCPServerConfig, StdioMCPConfig
from devboard.mcp.mcp_lifecycle import _unwrap_exception_group


class TestUnwrapExceptionGroup:
    def test_unwraps_single_exception_group(self) -> None:
        original = ValueError("bad command args")
        group = ExceptionGroup("task group error", [original])
        result = _unwrap_exception_group(group)
        assert result is original

    def test_unwraps_nested_single_exception_groups(self) -> None:
        original = RuntimeError("connection refused")
        inner = ExceptionGroup("inner", [original])
        outer = ExceptionGroup("outer", [inner])
        result = _unwrap_exception_group(outer)
        assert result is original

    def test_returns_plain_exception_unchanged(self) -> None:
        original = ValueError("simple error")
        result = _unwrap_exception_group(original)
        assert result is original

    def test_multi_exception_group_returned_as_is(self) -> None:
        group = ExceptionGroup("multiple", [ValueError("a"), TypeError("b")])
        result = _unwrap_exception_group(group)
        assert result is group


class TestMCPLifecycleManagerOAuthSupport:
    """Tests for MCPLifecycleManager's OAuth authentication support."""

    def test_http_config_with_oauth_and_provider_creates_client_with_auth(self):
        """Test HTTP config with auth_type='oauth' and oauth_provider creates client with auth."""
        mock_server_config = Mock(spec=MCPServerConfig)
        mock_server_config.name = "test-oauth-server"
        http_config = HttpMCPConfig(
            url="https://mcp.example.com",
            auth_type="oauth",
            client_id="test-client-id",
            client_secret="test-client-secret",
            scopes="read write",
        )
        mock_server_config.config = http_config

        mock_oauth_provider = Mock()

        with (
            patch("devboard.mcp.mcp_lifecycle.streamable_http_client") as mock_streamable_client,
            patch("devboard.mcp.mcp_lifecycle.httpx.AsyncClient") as mock_async_client,
        ):
            mock_http_client_instance = Mock()
            mock_async_client.return_value = mock_http_client_instance

            from devboard.mcp.mcp_lifecycle import MCPLifecycleManager

            MCPLifecycleManager(
                server_config=mock_server_config,
                oauth_provider=mock_oauth_provider,
            )

            mock_async_client.assert_called_once_with(auth=mock_oauth_provider)

            mock_streamable_client.assert_called_once_with(
                "https://mcp.example.com",
                http_client=mock_http_client_instance,
            )

    def test_http_config_with_bearer_creates_client_with_bearer_header(self):
        """Test HTTP config with auth_type='bearer' creates client with bearer token header."""
        mock_server_config = Mock(spec=MCPServerConfig)
        mock_server_config.name = "test-bearer-server"
        http_config = HttpMCPConfig(
            url="https://mcp.example.com",
            auth_type="bearer",
            bearer_token="test-bearer-token",
        )
        mock_server_config.config = http_config

        with (
            patch("devboard.mcp.mcp_lifecycle.streamable_http_client") as mock_streamable_client,
            patch("devboard.mcp.mcp_lifecycle.httpx.AsyncClient") as mock_async_client,
        ):
            mock_http_client_instance = Mock()
            mock_async_client.return_value = mock_http_client_instance

            from devboard.mcp.mcp_lifecycle import MCPLifecycleManager

            MCPLifecycleManager(
                server_config=mock_server_config,
                oauth_provider=None,
            )

            mock_async_client.assert_called_once_with(headers={"Authorization": "Bearer test-bearer-token"})

            mock_streamable_client.assert_called_once_with(
                "https://mcp.example.com",
                http_client=mock_http_client_instance,
            )

    def test_http_config_with_none_auth_creates_client_without_auth(self):
        """Test HTTP config with auth_type='none' creates client without auth."""
        mock_server_config = Mock(spec=MCPServerConfig)
        mock_server_config.name = "test-no-auth-server"
        http_config = HttpMCPConfig(
            url="https://mcp.example.com",
            auth_type="none",
        )
        mock_server_config.config = http_config

        with (
            patch("devboard.mcp.mcp_lifecycle.streamable_http_client") as mock_streamable_client,
            patch("devboard.mcp.mcp_lifecycle.httpx.AsyncClient") as mock_async_client,
        ):
            from devboard.mcp.mcp_lifecycle import MCPLifecycleManager

            MCPLifecycleManager(
                server_config=mock_server_config,
                oauth_provider=None,
            )

            mock_async_client.assert_not_called()

            mock_streamable_client.assert_called_once_with(
                "https://mcp.example.com",
                http_client=None,
            )

    def test_http_config_with_oauth_but_no_provider_creates_client_without_auth(self):
        """Test HTTP config with auth_type='oauth' but NO oauth_provider creates client without auth (fallback)."""
        mock_server_config = Mock(spec=MCPServerConfig)
        mock_server_config.name = "test-oauth-no-provider-server"
        http_config = HttpMCPConfig(
            url="https://mcp.example.com",
            auth_type="oauth",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )
        mock_server_config.config = http_config

        with (
            patch("devboard.mcp.mcp_lifecycle.streamable_http_client") as mock_streamable_client,
            patch("devboard.mcp.mcp_lifecycle.httpx.AsyncClient") as mock_async_client,
        ):
            from devboard.mcp.mcp_lifecycle import MCPLifecycleManager

            MCPLifecycleManager(
                server_config=mock_server_config,
                oauth_provider=None,
            )

            mock_async_client.assert_not_called()

            mock_streamable_client.assert_called_once_with(
                "https://mcp.example.com",
                http_client=None,
            )

    def test_stdio_config_is_unaffected_by_oauth_provider(self):
        """Test STDIO config is unaffected by oauth_provider parameter."""
        mock_server_config = Mock(spec=MCPServerConfig)
        mock_server_config.name = "test-stdio-server"
        stdio_config = StdioMCPConfig(
            command="python",
            args=["-m", "mcp.server"],
            env={"PATH": "/usr/bin"},
        )
        mock_server_config.config = stdio_config

        mock_oauth_provider = Mock()

        with (
            patch("devboard.mcp.mcp_lifecycle.stdio_client") as mock_stdio_client,
            patch("devboard.mcp.mcp_lifecycle.StdioServerParameters") as mock_stdio_params,
            patch("devboard.mcp.mcp_lifecycle.httpx.AsyncClient") as mock_async_client,
        ):
            mock_params_instance = Mock()
            mock_stdio_params.return_value = mock_params_instance

            from devboard.mcp.mcp_lifecycle import MCPLifecycleManager

            MCPLifecycleManager(
                server_config=mock_server_config,
                oauth_provider=mock_oauth_provider,
            )

            mock_stdio_params.assert_called_once_with(
                command="python",
                args=["-m", "mcp.server"],
                env={"PATH": "/usr/bin"},
            )

            mock_stdio_client.assert_called_once_with(mock_params_instance)

            mock_async_client.assert_not_called()

    def test_http_config_with_bearer_but_no_token_creates_client_without_auth(self):
        """Test HTTP config with auth_type='bearer' but no bearer_token creates client without auth."""
        mock_server_config = Mock(spec=MCPServerConfig)
        mock_server_config.name = "test-bearer-no-token-server"
        http_config = HttpMCPConfig(
            url="https://mcp.example.com",
            auth_type="bearer",
            bearer_token=None,
        )
        mock_server_config.config = http_config

        with (
            patch("devboard.mcp.mcp_lifecycle.streamable_http_client") as mock_streamable_client,
            patch("devboard.mcp.mcp_lifecycle.httpx.AsyncClient") as mock_async_client,
        ):
            from devboard.mcp.mcp_lifecycle import MCPLifecycleManager

            MCPLifecycleManager(
                server_config=mock_server_config,
                oauth_provider=None,
            )

            mock_async_client.assert_not_called()

            mock_streamable_client.assert_called_once_with(
                "https://mcp.example.com",
                http_client=None,
            )

    def test_http_config_with_oauth_provider_takes_precedence_over_bearer(self):
        """Test that OAuth auth is used even if bearer_token is also set when oauth_provider is available."""
        mock_server_config = Mock(spec=MCPServerConfig)
        mock_server_config.name = "test-oauth-precedence-server"
        http_config = HttpMCPConfig(
            url="https://mcp.example.com",
            auth_type="oauth",
            bearer_token="should-be-ignored",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )
        mock_server_config.config = http_config

        mock_oauth_provider = Mock()

        with (
            patch("devboard.mcp.mcp_lifecycle.streamable_http_client") as mock_streamable_client,
            patch("devboard.mcp.mcp_lifecycle.httpx.AsyncClient") as mock_async_client,
        ):
            mock_http_client_instance = Mock()
            mock_async_client.return_value = mock_http_client_instance

            from devboard.mcp.mcp_lifecycle import MCPLifecycleManager

            MCPLifecycleManager(
                server_config=mock_server_config,
                oauth_provider=mock_oauth_provider,
            )

            mock_async_client.assert_called_once_with(auth=mock_oauth_provider)

            mock_streamable_client.assert_called_once_with(
                "https://mcp.example.com",
                http_client=mock_http_client_instance,
            )
