"""Tests for MCP OAuth adapter factory functions and handlers."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.mcp.mcp_oauth_adapter import (
    create_mcp_callback_handler,
    create_mcp_redirect_handler,
    create_oauth_provider,
)
from devboard.services.oauth_service import OAuthService


class TestCreateOAuthProvider:
    """Tests for create_oauth_provider factory function."""

    @pytest.mark.asyncio
    async def test_creates_oauth_provider_with_correct_parameters(self):
        """Test that create_oauth_provider creates an OAuthClientProvider with correct parameters."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.generate_mcp_provider_key = OAuthService.generate_mcp_provider_key

        with (
            patch("devboard.mcp.mcp_oauth_adapter.OAuthClientProvider") as mock_provider_class,
            patch("devboard.mcp.mcp_oauth_adapter.OAuthClientMetadata") as mock_metadata_class,
            patch("devboard.mcp.mcp_oauth_adapter.MCPTokenStorageAdapter") as mock_storage_class,
        ):
            mock_provider_instance = Mock()
            mock_provider_class.return_value = mock_provider_instance
            mock_metadata_instance = Mock()
            mock_metadata_class.return_value = mock_metadata_instance
            mock_storage_instance = Mock()
            mock_storage_instance.set_client_info = AsyncMock()
            mock_storage_class.return_value = mock_storage_instance

            result = await create_oauth_provider(
                server_id=123,
                server_url="https://mcp.example.com",
                oauth_service=mock_oauth_service,
                backend_base_url="http://localhost:8000",
                scopes="read write",
            )

            # Verify provider was created with correct arguments
            assert result == mock_provider_instance
            mock_provider_class.assert_called_once()
            call_kwargs = mock_provider_class.call_args[1]

            assert call_kwargs["server_url"] == "https://mcp.example.com"
            assert call_kwargs["client_metadata"] == mock_metadata_instance
            assert call_kwargs["storage"] == mock_storage_instance
            assert "redirect_handler" in call_kwargs
            assert "callback_handler" in call_kwargs

            # Verify metadata was created with correct arguments
            mock_metadata_class.assert_called_once()
            metadata_kwargs = mock_metadata_class.call_args[1]
            assert metadata_kwargs["client_name"] == "DevBoard"
            assert metadata_kwargs["redirect_uris"] == ["http://localhost:8000/api/oauth/callback/mcp-123"]
            assert metadata_kwargs["grant_types"] == ["authorization_code", "refresh_token"]
            assert metadata_kwargs["response_types"] == ["code"]
            assert metadata_kwargs["scope"] == "read write"

            # Verify storage was created with correct arguments
            mock_storage_class.assert_called_once_with(mock_oauth_service, "mcp-123")

    @pytest.mark.asyncio
    async def test_pre_seeds_client_info_when_client_id_provided(self):
        """Test that create_oauth_provider pre-seeds client info when client_id is provided."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.generate_mcp_provider_key = OAuthService.generate_mcp_provider_key

        with (
            patch("devboard.mcp.mcp_oauth_adapter.OAuthClientProvider"),
            patch("devboard.mcp.mcp_oauth_adapter.OAuthClientMetadata"),
            patch("devboard.mcp.mcp_oauth_adapter.MCPTokenStorageAdapter") as mock_storage_class,
            patch("devboard.mcp.mcp_oauth_adapter.OAuthClientInformationFull") as mock_client_info_class,
        ):
            mock_storage_instance = Mock()
            mock_storage_instance.set_client_info = AsyncMock()
            mock_storage_class.return_value = mock_storage_instance
            mock_client_info_instance = Mock()
            mock_client_info_class.return_value = mock_client_info_instance

            await create_oauth_provider(
                server_id=456,
                server_url="https://mcp.example.com",
                oauth_service=mock_oauth_service,
                backend_base_url="http://localhost:8000",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )

            # Verify client info was created with correct arguments
            mock_client_info_class.assert_called_once_with(
                client_id="test-client-id",
                client_secret="test-client-secret",
                redirect_uris=["http://localhost:8000/api/oauth/callback/mcp-456"],
            )

            # Verify client info was stored
            mock_storage_instance.set_client_info.assert_called_once_with(mock_client_info_instance)

    @pytest.mark.asyncio
    async def test_does_not_pre_seed_when_no_client_id_provided(self):
        """Test that create_oauth_provider doesn't pre-seed client info when no client_id provided."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.generate_mcp_provider_key = OAuthService.generate_mcp_provider_key

        with (
            patch("devboard.mcp.mcp_oauth_adapter.OAuthClientProvider"),
            patch("devboard.mcp.mcp_oauth_adapter.OAuthClientMetadata"),
            patch("devboard.mcp.mcp_oauth_adapter.MCPTokenStorageAdapter") as mock_storage_class,
        ):
            mock_storage_instance = Mock()
            mock_storage_instance.set_client_info = AsyncMock()
            mock_storage_class.return_value = mock_storage_instance

            await create_oauth_provider(
                server_id=789,
                server_url="https://mcp.example.com",
                oauth_service=mock_oauth_service,
                backend_base_url="http://localhost:8000",
            )

            # Verify client info was NOT stored
            mock_storage_instance.set_client_info.assert_not_called()


class TestCreateMcpRedirectHandler:
    """Tests for create_mcp_redirect_handler function."""

    def test_returns_async_callable(self):
        """Test that create_mcp_redirect_handler returns an async callable."""
        mock_oauth_service = Mock(spec=OAuthService)

        handler = create_mcp_redirect_handler(
            provider_key="mcp-123",
            oauth_service=mock_oauth_service,
            redirect_uri="http://localhost:8000/callback",
        )

        # Verify it's a callable
        assert callable(handler)

        # Verify it's a coroutine function
        import inspect

        assert inspect.iscoroutinefunction(handler)

    @pytest.mark.asyncio
    async def test_handler_creates_pending_authorization_and_opens_browser(self):
        """Test that the redirect handler creates pending authorization and opens browser."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.create_pending_authorization = Mock()

        handler = create_mcp_redirect_handler(
            provider_key="mcp-456",
            oauth_service=mock_oauth_service,
            redirect_uri="http://localhost:8000/callback",
        )

        authorization_url = "https://example.com/oauth/authorize?state=test-state-abc&client_id=123"

        with patch("devboard.mcp.mcp_oauth_adapter.webbrowser.open") as mock_browser_open:
            await handler(authorization_url)

            # Verify pending authorization was created with extracted state
            mock_oauth_service.create_pending_authorization.assert_called_once_with(
                provider_key="mcp-456",
                state="test-state-abc",
                redirect_uri="http://localhost:8000/callback",
            )

            # Verify browser was opened with the URL
            mock_browser_open.assert_called_once_with(authorization_url)

    @pytest.mark.asyncio
    async def test_handler_handles_url_without_state(self):
        """Test that the redirect handler handles URL without state parameter."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.create_pending_authorization = Mock()

        handler = create_mcp_redirect_handler(
            provider_key="mcp-789",
            oauth_service=mock_oauth_service,
            redirect_uri="http://localhost:8000/callback",
        )

        authorization_url = "https://example.com/oauth/authorize?client_id=123"

        with patch("devboard.mcp.mcp_oauth_adapter.webbrowser.open"):
            await handler(authorization_url)

            # Verify pending authorization was created with None state
            mock_oauth_service.create_pending_authorization.assert_called_once_with(
                provider_key="mcp-789",
                state=None,
                redirect_uri="http://localhost:8000/callback",
            )


class TestCreateMcpCallbackHandler:
    """Tests for create_mcp_callback_handler function."""

    @pytest.mark.asyncio
    async def test_returns_async_callable(self):
        """Test that create_mcp_callback_handler returns an async callable."""
        mock_oauth_service = Mock(spec=OAuthService)

        handler = await create_mcp_callback_handler(
            provider_key="mcp-123",
            oauth_service=mock_oauth_service,
        )

        # Verify it's a callable
        assert callable(handler)

        # Verify it's a coroutine function
        import inspect

        assert inspect.iscoroutinefunction(handler)

    @pytest.mark.asyncio
    async def test_handler_waits_for_authorization_code(self):
        """Test that the callback handler waits for authorization code."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.wait_for_authorization_code = AsyncMock(return_value=("auth-code-xyz", "state-123"))

        handler = await create_mcp_callback_handler(
            provider_key="mcp-456",
            oauth_service=mock_oauth_service,
            timeout_seconds=30.0,
        )

        code, state = await handler()

        # Verify wait_for_authorization_code was called with correct parameters
        mock_oauth_service.wait_for_authorization_code.assert_called_once_with(
            provider_key="mcp-456",
            timeout_seconds=30.0,
        )

        # Verify returned values
        assert code == "auth-code-xyz"
        assert state == "state-123"

    @pytest.mark.asyncio
    async def test_handler_uses_default_timeout(self):
        """Test that the callback handler uses default timeout when not specified."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.wait_for_authorization_code = AsyncMock(return_value=("auth-code", "state"))

        handler = await create_mcp_callback_handler(
            provider_key="mcp-789",
            oauth_service=mock_oauth_service,
        )

        await handler()

        # Verify default timeout of 60.0 was used
        mock_oauth_service.wait_for_authorization_code.assert_called_once_with(
            provider_key="mcp-789",
            timeout_seconds=60.0,
        )

    @pytest.mark.asyncio
    async def test_handler_propagates_timeout_error(self):
        """Test that the callback handler propagates timeout errors."""
        mock_oauth_service = Mock(spec=OAuthService)
        mock_oauth_service.wait_for_authorization_code = AsyncMock(side_effect=TimeoutError("Authorization timeout"))

        handler = await create_mcp_callback_handler(
            provider_key="mcp-timeout",
            oauth_service=mock_oauth_service,
        )

        with pytest.raises(TimeoutError):
            await handler()
