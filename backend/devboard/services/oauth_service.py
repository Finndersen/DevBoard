"""Service for managing OAuth authentication flows."""

import asyncio
import datetime
import hashlib
import json
import secrets
import urllib.parse
from base64 import urlsafe_b64encode
from dataclasses import dataclass

import httpx
import logfire

from devboard.db.models import OAuthClientInfo, OAuthProvider, OAuthToken, PendingOAuthAuthorization
from devboard.db.repositories.oauth import OAuthRepository


@dataclass
class TokenData:
    """Data class for token information."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime.datetime | None = None
    scopes: str | None = None
    raw_response: str | None = None


class OAuthFlowError(Exception):
    """Exception raised during OAuth flow execution."""

    pass


class OAuthStateMismatchError(Exception):
    """Exception raised when OAuth state parameter doesn't match expected value."""

    pass


class OAuthService:
    """Service for managing OAuth authentication flows."""

    def __init__(self, oauth_repo: OAuthRepository):
        """Initialize the OAuth service.

        Args:
            oauth_repo: Repository for OAuth data access
        """
        self.oauth_repo = oauth_repo

    # Provider key helpers

    @staticmethod
    def generate_oauth_provider_key(provider_id: int) -> str:
        """Generate a provider key for static OAuth providers.

        Args:
            provider_id: The OAuth provider ID

        Returns:
            Provider key string (e.g., "oauth-1")
        """
        return f"oauth-{provider_id}"

    @staticmethod
    def generate_mcp_provider_key(mcp_server_id: int) -> str:
        """Generate a provider key for MCP servers.

        Args:
            mcp_server_id: The MCP server config ID

        Returns:
            Provider key string (e.g., "mcp-1")
        """
        return f"mcp-{mcp_server_id}"

    # Pending Authorization operations

    def create_pending_authorization(
        self,
        provider_key: str,
        state: str | None = None,
        code_verifier: str | None = None,
        redirect_uri: str | None = None,
    ) -> PendingOAuthAuthorization:
        """Create a new pending OAuth authorization.

        Args:
            provider_key: Unique identifier for the OAuth context
            state: OAuth state parameter for CSRF protection
            code_verifier: PKCE code verifier if using PKCE
            redirect_uri: The callback URI for this flow

        Returns:
            Created PendingOAuthAuthorization record
        """
        return self.oauth_repo.create_pending_authorization(
            provider_key=provider_key,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        )

    def store_authorization_code(
        self,
        provider_key: str,
        authorization_code: str,
        state: str | None = None,
    ) -> PendingOAuthAuthorization | None:
        """Store the authorization code received from callback.

        Args:
            provider_key: The provider key for this flow
            authorization_code: The authorization code from the OAuth callback
            state: Optional state parameter to validate

        Returns:
            Updated PendingOAuthAuthorization or None if not found

        Raises:
            OAuthStateMismatchError: If state parameter doesn't match expected value
        """
        pending = self.oauth_repo.get_pending_authorization(provider_key)
        if not pending:
            logfire.warn(f"No pending authorization found for provider_key:{provider_key}")
            return None

        # Validate state if both are present
        if pending.state and state and pending.state != state:
            logfire.warn(f"State mismatch for provider_key:{provider_key}")
            raise OAuthStateMismatchError(f"State parameter mismatch for provider {provider_key}")

        pending.authorization_code = authorization_code
        return self.oauth_repo.update_pending_authorization(pending)

    async def wait_for_authorization_code(
        self,
        provider_key: str,
        timeout_seconds: float = 60.0,
        poll_interval: float = 0.5,
    ) -> tuple[str, str | None]:
        """Wait for the authorization code to be received via callback.

        Args:
            provider_key: The provider key for this flow
            timeout_seconds: Maximum time to wait
            poll_interval: Time between polls

        Returns:
            Tuple of (authorization_code, state)

        Raises:
            TimeoutError: If callback not received within timeout
            OAuthFlowError: If pending authorization not found
        """
        iterations = int(timeout_seconds / poll_interval)

        for _ in range(iterations):
            pending = self.oauth_repo.get_pending_authorization(provider_key)
            if not pending:
                raise OAuthFlowError(f"No pending authorization found for provider_key:{provider_key}")

            if pending.authorization_code:
                code = pending.authorization_code
                state = pending.state
                # Clean up the pending record
                self.oauth_repo.delete_pending_authorization(provider_key)
                return (code, state)

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"OAuth callback not received within {timeout_seconds} seconds")

    def delete_pending_authorization(self, provider_key: str) -> bool:
        """Delete a pending authorization.

        Args:
            provider_key: The provider key

        Returns:
            True if deleted, False if not found
        """
        return self.oauth_repo.delete_pending_authorization(provider_key)

    def get_pending_authorization(self, provider_key: str) -> PendingOAuthAuthorization | None:
        """Get a pending authorization by provider key.

        Args:
            provider_key: The provider key

        Returns:
            PendingOAuthAuthorization if found, None otherwise
        """
        return self.oauth_repo.get_pending_authorization(provider_key)

    # Token operations

    def get_tokens(self, provider_key: str) -> OAuthToken | None:
        """Get stored tokens for a provider.

        Args:
            provider_key: The provider key

        Returns:
            OAuthToken if found, None otherwise
        """
        return self.oauth_repo.get_token_by_provider_key(provider_key)

    def store_tokens(self, provider_key: str, token_data: TokenData) -> OAuthToken:
        """Store tokens for a provider.

        Args:
            provider_key: The provider key
            token_data: Token data to store

        Returns:
            Created or updated OAuthToken
        """
        return self.oauth_repo.upsert_token(
            provider_key=provider_key,
            access_token=token_data.access_token,
            refresh_token=token_data.refresh_token,
            token_type=token_data.token_type,
            expires_at=token_data.expires_at,
            scopes=token_data.scopes,
            raw_token_response=token_data.raw_response,
        )

    def is_token_expired(self, provider_key: str) -> bool:
        """Check if a token is expired.

        Args:
            provider_key: The provider key

        Returns:
            True if token is expired or not found, False if valid
        """
        token = self.oauth_repo.get_token_by_provider_key(provider_key)
        if not token:
            return True

        if not token.expires_at:
            # No expiration set, assume valid
            return False

        # Ensure expires_at has timezone info for comparison
        expires_at = token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.UTC)

        # Add a small buffer (5 minutes) to avoid edge cases
        buffer = datetime.timedelta(minutes=5)
        return datetime.datetime.now(datetime.UTC) >= (expires_at - buffer)

    def delete_tokens(self, provider_key: str) -> bool:
        """Delete tokens for a provider.

        Args:
            provider_key: The provider key

        Returns:
            True if deleted, False if not found
        """
        return self.oauth_repo.delete_token(provider_key)

    # Client Info operations

    def get_client_info(self, provider_key: str) -> OAuthClientInfo | None:
        """Get client info for a provider.

        Args:
            provider_key: The provider key

        Returns:
            OAuthClientInfo if found, None otherwise
        """
        return self.oauth_repo.get_client_info_by_provider_key(provider_key)

    def store_client_info(self, provider_key: str, raw_client_info: str) -> OAuthClientInfo:
        """Store client info for a provider.

        Args:
            provider_key: The provider key
            raw_client_info: Full client registration response JSON

        Returns:
            Created or updated OAuthClientInfo
        """
        return self.oauth_repo.upsert_client_info(
            provider_key=provider_key,
            raw_client_info=raw_client_info,
        )

    def delete_client_info(self, provider_key: str) -> bool:
        """Delete client info for a provider.

        Args:
            provider_key: The provider key

        Returns:
            True if deleted, False if not found
        """
        return self.oauth_repo.delete_client_info(provider_key)

    # OAuth Provider operations

    def get_oauth_provider(self, provider_id: int) -> OAuthProvider | None:
        """Get an OAuth provider by ID.

        Args:
            provider_id: The provider ID

        Returns:
            OAuthProvider if found, None otherwise
        """
        return self.oauth_repo.get_oauth_provider(provider_id)

    def list_oauth_providers(self) -> list[OAuthProvider]:
        """List all OAuth providers.

        Returns:
            List of OAuthProvider instances
        """
        return self.oauth_repo.list_oauth_providers()

    # Traditional OAuth Flow operations

    def initiate_oauth_flow(
        self,
        oauth_provider_id: int,
        redirect_uri: str,
        use_pkce: bool = True,
    ) -> str:
        """Initiate a traditional OAuth flow for a static provider.

        Args:
            oauth_provider_id: The OAuth provider ID
            redirect_uri: The callback URI for this flow
            use_pkce: Whether to use PKCE (default: True)

        Returns:
            Authorization URL for user to visit

        Raises:
            OAuthFlowError: If provider not found
        """
        provider = self.oauth_repo.get_oauth_provider(oauth_provider_id)
        if not provider:
            raise OAuthFlowError(f"OAuth provider not found: {oauth_provider_id}")

        provider_key = self.generate_oauth_provider_key(oauth_provider_id)

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Generate PKCE parameters if enabled
        code_verifier = None
        code_challenge = None
        if use_pkce:
            code_verifier = secrets.token_urlsafe(64)
            # Create code challenge using S256 method
            code_challenge = urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")

        # Create pending authorization record
        self.create_pending_authorization(
            provider_key=provider_key,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        )

        # Build authorization URL
        params = {
            "client_id": provider.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": provider.scopes,
            "state": state,
        }

        if use_pkce and code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        auth_url = f"{provider.authorization_url}?{urllib.parse.urlencode(params)}"
        logfire.info(f"Initiated OAuth flow for provider:{provider.name} provider_key:{provider_key}")

        return auth_url

    async def complete_oauth_flow(
        self,
        provider_key: str,
        timeout_seconds: float = 60.0,
    ) -> OAuthToken:
        """Complete a traditional OAuth flow by waiting for callback and exchanging code.

        Args:
            provider_key: The provider key (e.g., "oauth-1")
            timeout_seconds: Maximum time to wait for callback

        Returns:
            OAuthToken with the stored tokens

        Raises:
            OAuthFlowError: If flow fails
            TimeoutError: If callback not received
        """
        # Extract provider ID from key
        if not provider_key.startswith("oauth-"):
            raise OAuthFlowError(f"Invalid provider key format: {provider_key}")

        try:
            provider_id = int(provider_key.split("-")[1])
        except (IndexError, ValueError) as e:
            raise OAuthFlowError(f"Invalid provider key format: {provider_key}") from e

        provider = self.oauth_repo.get_oauth_provider(provider_id)
        if not provider:
            raise OAuthFlowError(f"OAuth provider not found: {provider_id}")

        # Get pending authorization for code verifier and redirect_uri
        pending = self.oauth_repo.get_pending_authorization(provider_key)
        if not pending:
            raise OAuthFlowError(f"No pending authorization found for: {provider_key}")

        code_verifier = pending.code_verifier
        redirect_uri = pending.redirect_uri

        # Wait for authorization code
        authorization_code, _ = await self.wait_for_authorization_code(
            provider_key=provider_key,
            timeout_seconds=timeout_seconds,
        )

        # Exchange code for tokens
        token_data = await self._exchange_code_for_tokens(
            provider=provider,
            authorization_code=authorization_code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

        # Store and return tokens
        return self.store_tokens(provider_key, token_data)

    async def _exchange_code_for_tokens(
        self,
        provider: OAuthProvider,
        authorization_code: str,
        redirect_uri: str | None,
        code_verifier: str | None,
    ) -> TokenData:
        """Exchange an authorization code for tokens.

        Args:
            provider: The OAuth provider
            authorization_code: The authorization code
            redirect_uri: The redirect URI used in the initial request
            code_verifier: PKCE code verifier if used

        Returns:
            TokenData with the tokens

        Raises:
            OAuthFlowError: If token exchange fails
        """
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
        }

        if redirect_uri:
            data["redirect_uri"] = redirect_uri

        if code_verifier:
            data["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    provider.token_url,
                    data=data,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise OAuthFlowError(f"Token exchange failed: {e}") from e

            token_response = response.json()

        # Parse token response
        access_token = token_response.get("access_token")
        if not access_token:
            raise OAuthFlowError("No access_token in token response")

        expires_at = None
        if "expires_in" in token_response:
            expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=token_response["expires_in"])

        return TokenData(
            access_token=access_token,
            refresh_token=token_response.get("refresh_token"),
            token_type=token_response.get("token_type", "Bearer"),
            expires_at=expires_at,
            scopes=token_response.get("scope"),
            raw_response=json.dumps(token_response),
        )

    # Maintenance operations

    def cleanup_expired_pending_authorizations(self, max_age_seconds: int = 600) -> int:
        """Clean up expired pending authorizations.

        Args:
            max_age_seconds: Maximum age in seconds (default: 10 minutes)

        Returns:
            Number of deleted records
        """
        return self.oauth_repo.delete_expired_pending_authorizations(max_age_seconds)
