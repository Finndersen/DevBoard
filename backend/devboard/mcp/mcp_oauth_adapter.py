"""MCP OAuth adapter implementing the TokenStorage protocol."""

import datetime
import json
import urllib.parse
import webbrowser
from collections.abc import Awaitable, Callable

import logfire
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata
from mcp.shared.auth import OAuthToken as MCPOAuthToken

from devboard.services.oauth_service import OAuthService, TokenData


class MCPTokenStorageAdapter:
    """Adapter implementing MCP SDK's TokenStorage protocol using DevBoard's OAuth framework.

    This adapter translates between MCP's OAuth types and DevBoard's normalized database models,
    allowing the MCP SDK to use DevBoard's OAuth infrastructure for token storage.
    """

    def __init__(self, oauth_service: OAuthService, provider_key: str):
        """Initialize the adapter.

        Args:
            oauth_service: DevBoard's OAuth service for data access
            provider_key: Unique identifier for this MCP server (e.g., "mcp-1")
        """
        self.oauth_service = oauth_service
        self.provider_key = provider_key

    async def get_tokens(self) -> MCPOAuthToken | None:
        """Get stored tokens.

        Returns:
            MCPOAuthToken if tokens exist, None otherwise
        """
        db_token = self.oauth_service.get_tokens(self.provider_key)
        if not db_token:
            return None

        # Convert DB token to MCP token
        # Note: MCP expects expires_in (seconds), not expires_at (datetime)
        expires_in = None
        if db_token.expires_at:
            now = datetime.datetime.now(datetime.UTC)
            # Ensure expires_at has timezone info for comparison
            expires_at = db_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.UTC)
            delta = expires_at - now
            expires_in = max(0, int(delta.total_seconds()))

        return MCPOAuthToken(
            access_token=db_token.access_token,
            token_type=db_token.token_type,
            expires_in=expires_in,
            scope=db_token.scopes,
            refresh_token=db_token.refresh_token,
        )

    async def set_tokens(self, tokens: MCPOAuthToken) -> None:
        """Store tokens.

        Args:
            tokens: MCP OAuth token to store
        """
        # Convert MCP token to TokenData
        expires_at = None
        if tokens.expires_in:
            expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=tokens.expires_in)

        token_data = TokenData(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_at=expires_at,
            scopes=tokens.scope,
            raw_response=tokens.model_dump_json(),
        )

        self.oauth_service.store_tokens(self.provider_key, token_data)
        logfire.info(f"Stored MCP tokens for provider_key:{self.provider_key}")

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Get stored client information.

        Returns:
            OAuthClientInformationFull if client info exists, None otherwise
        """
        db_client_info = self.oauth_service.get_client_info(self.provider_key)
        if not db_client_info:
            return None

        # Deserialize from JSON
        try:
            data = json.loads(db_client_info.raw_client_info)
            return OAuthClientInformationFull.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logfire.error(f"Failed to deserialize client info for {self.provider_key}: {e}")
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information.

        Args:
            client_info: MCP OAuth client information to store
        """
        raw_json = client_info.model_dump_json()
        self.oauth_service.store_client_info(self.provider_key, raw_json)
        logfire.info(f"Stored MCP client info for provider_key:{self.provider_key}")


def create_mcp_redirect_handler(
    provider_key: str,
    oauth_service: OAuthService,
    redirect_uri: str,
) -> Callable[[str], Awaitable[None]]:
    """Create a redirect handler for MCP OAuth flow.

    The redirect handler opens the authorization URL in the user's browser
    and creates the pending authorization record.

    Args:
        provider_key: The provider key for this MCP server
        oauth_service: DevBoard's OAuth service
        redirect_uri: The callback URI for this flow

    Returns:
        Async function that handles redirects
    """

    async def handle_redirect(authorization_url: str) -> None:
        """Handle redirect by opening browser and creating pending record."""
        # Parse the authorization URL to extract state parameter
        parsed = urllib.parse.urlparse(authorization_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        state = query_params.get("state", [None])[0]

        # Create pending authorization record before redirecting
        oauth_service.create_pending_authorization(
            provider_key=provider_key,
            state=state,
            redirect_uri=redirect_uri,
        )

        logfire.info(f"Opening browser for OAuth flow: provider_key:{provider_key}")

        # Open URL in user's default browser
        webbrowser.open(authorization_url)

    return handle_redirect


async def create_mcp_callback_handler(
    provider_key: str,
    oauth_service: OAuthService,
    timeout_seconds: float = 60.0,
) -> Callable[[], Awaitable[tuple[str, str | None]]]:
    """Create a callback handler for MCP OAuth flow.

    The callback handler polls for the authorization code that gets stored
    by the callback endpoint.

    Args:
        provider_key: The provider key for this MCP server
        oauth_service: DevBoard's OAuth service
        timeout_seconds: Maximum time to wait for callback

    Returns:
        Async function that waits for and returns the authorization code
    """

    async def handle_callback() -> tuple[str, str | None]:
        """Wait for the callback and return the authorization code.

        Returns:
            Tuple of (authorization_code, state)

        Raises:
            TimeoutError: If callback not received within timeout
        """
        return await oauth_service.wait_for_authorization_code(
            provider_key=provider_key,
            timeout_seconds=timeout_seconds,
        )

    return handle_callback


async def create_oauth_provider(
    server_id: int,
    server_url: str,
    oauth_service: OAuthService,
    backend_base_url: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    scopes: str | None = None,
) -> OAuthClientProvider:
    """Create an OAuthClientProvider for an MCP server.

    When client_id/client_secret are provided, they are pre-seeded into storage
    so the SDK skips Dynamic Client Registration.
    """
    provider_key = OAuthService.generate_mcp_provider_key(server_id)
    redirect_uri = f"{backend_base_url}/api/oauth/callback/{provider_key}"

    client_metadata = OAuthClientMetadata(
        client_name="DevBoard",
        redirect_uris=[redirect_uri],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        scope=scopes,
    )

    storage = MCPTokenStorageAdapter(oauth_service, provider_key)

    # Pre-seed client info if manual credentials are provided
    if client_id:
        client_info = OAuthClientInformationFull(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=[redirect_uri],
        )
        await storage.set_client_info(client_info)

    redirect_handler = create_mcp_redirect_handler(provider_key, oauth_service, redirect_uri)
    callback_handler = await create_mcp_callback_handler(provider_key, oauth_service)

    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
