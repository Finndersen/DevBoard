"""Integration tests for OAuth authentication framework."""

import asyncio
import datetime
import json

import pytest
from sqlalchemy.orm import Session

from devboard.db.models import (
    MCPServerConfig,
    MCPServerType,
    OAuthProvider,
    OAuthProviderType,
)
from devboard.db.repositories import MCPServerRepository, OAuthRepository
from devboard.services.mcp_oauth_adapter import MCPTokenStorageAdapter
from devboard.services.oauth_service import OAuthService, TokenData


class TestOAuthCallbackEndpoint:
    """Tests for OAuth callback endpoint."""

    def test_callback_receives_and_stores_authorization_code(self, client, db_session: Session):
        """Test that callback endpoint receives and stores authorization code."""
        # Create pending authorization first
        oauth_repo = OAuthRepository(db_session)
        oauth_service = OAuthService(oauth_repo)

        provider_key = "mcp-123"
        state = "test-state-abc123"

        oauth_service.create_pending_authorization(
            provider_key=provider_key,
            state=state,
            redirect_uri="http://localhost:8000/api/oauth/callback/mcp-123",
        )
        db_session.commit()

        # Simulate callback from OAuth provider
        response = client.get(
            f"/api/oauth/callback/{provider_key}",
            params={"code": "auth-code-xyz", "state": state},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider_key"] == provider_key
        assert "successfully" in data["message"].lower()

    def test_callback_without_code_returns_error(self, client, db_session: Session):
        """Test that callback without code returns error."""
        response = client.get("/api/oauth/callback/mcp-123")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_callback_with_error_returns_error(self, client, db_session: Session):
        """Test that callback with error parameter returns error."""
        response = client.get(
            "/api/oauth/callback/mcp-123",
            params={"error": "access_denied", "error_description": "User denied access"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_callback_without_pending_authorization_returns_404(self, client, db_session: Session):
        """Test that callback without pending authorization returns 404."""
        response = client.get(
            "/api/oauth/callback/nonexistent-provider",
            params={"code": "auth-code", "state": "test-state"},
        )

        assert response.status_code == 404

    def test_callback_with_state_mismatch_returns_400(self, client, db_session: Session):
        """Test that callback with mismatched state returns 400."""
        oauth_repo = OAuthRepository(db_session)
        oauth_service = OAuthService(oauth_repo)

        provider_key = "mcp-456"
        oauth_service.create_pending_authorization(
            provider_key=provider_key,
            state="expected-state",
            redirect_uri="http://localhost:8000/api/oauth/callback/mcp-456",
        )
        db_session.commit()

        # Simulate callback with wrong state
        response = client.get(
            f"/api/oauth/callback/{provider_key}",
            params={"code": "auth-code", "state": "wrong-state"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "state" in data["detail"]["error"].lower()


class TestMCPTokenStorageAdapter:
    """Tests for MCP TokenStorage adapter."""

    @pytest.fixture
    def oauth_repo(self, db_session: Session) -> OAuthRepository:
        return OAuthRepository(db_session)

    @pytest.fixture
    def oauth_service(self, oauth_repo: OAuthRepository) -> OAuthService:
        return OAuthService(oauth_repo)

    @pytest.fixture
    def adapter(self, oauth_service: OAuthService) -> MCPTokenStorageAdapter:
        return MCPTokenStorageAdapter(oauth_service, provider_key="mcp-test-1")

    @pytest.mark.asyncio
    async def test_set_and_get_tokens(self, adapter: MCPTokenStorageAdapter, db_session: Session):
        """Test storing and retrieving tokens via adapter."""
        from mcp.shared.auth import OAuthToken as MCPOAuthToken

        # Create token to store
        token = MCPOAuthToken(
            access_token="test-access-token",
            token_type="Bearer",
            expires_in=3600,
            scope="read write",
            refresh_token="test-refresh-token",
        )

        # Store token
        await adapter.set_tokens(token)
        db_session.commit()

        # Retrieve token
        retrieved = await adapter.get_tokens()

        assert retrieved is not None
        assert retrieved.access_token == "test-access-token"
        assert retrieved.token_type == "Bearer"
        assert retrieved.refresh_token == "test-refresh-token"
        assert retrieved.scope == "read write"
        # expires_in should be close to original (within tolerance for timing)
        assert retrieved.expires_in is not None
        assert retrieved.expires_in > 0

    @pytest.mark.asyncio
    async def test_get_tokens_returns_none_when_not_exists(self, adapter: MCPTokenStorageAdapter):
        """Test that get_tokens returns None when no tokens exist."""
        result = await adapter.get_tokens()
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_client_info(self, adapter: MCPTokenStorageAdapter, db_session: Session):
        """Test storing and retrieving client info via adapter."""
        from mcp.shared.auth import OAuthClientInformationFull

        # Create client info to store
        client_info = OAuthClientInformationFull(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uris=["http://localhost:8000/callback"],
        )

        # Store client info
        await adapter.set_client_info(client_info)
        db_session.commit()

        # Retrieve client info
        retrieved = await adapter.get_client_info()

        assert retrieved is not None
        assert retrieved.client_id == "test-client-id"
        assert retrieved.client_secret == "test-client-secret"
        # redirect_uris contains AnyUrl objects, so check string representation
        assert any("localhost:8000/callback" in str(uri) for uri in retrieved.redirect_uris)

    @pytest.mark.asyncio
    async def test_get_client_info_returns_none_when_not_exists(self, adapter: MCPTokenStorageAdapter):
        """Test that get_client_info returns None when no client info exists."""
        result = await adapter.get_client_info()
        assert result is None


class TestPollingMechanism:
    """Tests for authorization code polling mechanism."""

    @pytest.fixture
    def oauth_repo(self, db_session: Session) -> OAuthRepository:
        return OAuthRepository(db_session)

    @pytest.fixture
    def oauth_service(self, oauth_repo: OAuthRepository) -> OAuthService:
        return OAuthService(oauth_repo)

    @pytest.mark.asyncio
    async def test_polling_retrieves_stored_authorization_code(self, oauth_service: OAuthService, db_session: Session):
        """Test that polling retrieves authorization code after it's stored."""
        provider_key = "mcp-poll-test"

        # Create pending authorization
        oauth_service.create_pending_authorization(
            provider_key=provider_key,
            state="test-state",
        )
        db_session.commit()

        # Simulate callback storing the code in a separate task
        async def store_code_after_delay():
            await asyncio.sleep(0.2)
            oauth_service.store_authorization_code(
                provider_key=provider_key,
                authorization_code="polled-auth-code",
                state="test-state",
            )
            db_session.commit()

        # Start polling and code storage concurrently
        store_task = asyncio.create_task(store_code_after_delay())

        code, state = await oauth_service.wait_for_authorization_code(
            provider_key=provider_key,
            timeout_seconds=2.0,
            poll_interval=0.1,
        )

        await store_task

        assert code == "polled-auth-code"
        assert state == "test-state"

    @pytest.mark.asyncio
    async def test_polling_times_out_when_no_code_received(self, oauth_service: OAuthService, db_session: Session):
        """Test that polling times out if no code is received."""
        provider_key = "mcp-timeout-test"

        # Create pending authorization
        oauth_service.create_pending_authorization(provider_key=provider_key)
        db_session.commit()

        # Poll with short timeout
        with pytest.raises(TimeoutError):
            await oauth_service.wait_for_authorization_code(
                provider_key=provider_key,
                timeout_seconds=0.3,
                poll_interval=0.1,
            )


class TestOAuthRepository:
    """Tests for OAuth repository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> OAuthRepository:
        return OAuthRepository(db_session)

    def test_create_oauth_provider(self, repo: OAuthRepository):
        """Test creating an OAuth provider."""
        provider = OAuthProvider(
            name="Test Jira",
            provider_type=OAuthProviderType.JIRA,
            client_id="test-client-id",
            client_secret="test-client-secret",
            authorization_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            scopes="read:jira-work write:jira-work",
        )

        created = repo.create_oauth_provider(provider)

        assert created.id is not None
        assert created.name == "Test Jira"
        assert created.provider_type == OAuthProviderType.JIRA

    def test_upsert_token_creates_new(self, repo: OAuthRepository, db_session: Session):
        """Test upserting a token creates new record."""
        token = repo.upsert_token(
            provider_key="oauth-1",
            access_token="access-token-123",
            refresh_token="refresh-token-456",
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        )
        db_session.flush()

        assert token.id is not None
        assert token.access_token == "access-token-123"
        assert token.refresh_token == "refresh-token-456"

    def test_upsert_token_updates_existing(self, repo: OAuthRepository, db_session: Session):
        """Test upserting a token updates existing record."""
        # Create initial token
        token1 = repo.upsert_token(
            provider_key="oauth-1",
            access_token="access-token-v1",
        )
        db_session.flush()
        initial_id = token1.id

        # Update token
        token2 = repo.upsert_token(
            provider_key="oauth-1",
            access_token="access-token-v2",
        )
        db_session.flush()

        assert token2.id == initial_id  # Same record
        assert token2.access_token == "access-token-v2"

    def test_pending_authorization_lifecycle(self, repo: OAuthRepository, db_session: Session):
        """Test pending authorization create/update/delete lifecycle."""
        # Create
        pending = repo.create_pending_authorization(
            provider_key="oauth-lifecycle",
            state="test-state",
            code_verifier="test-verifier",
        )
        db_session.flush()
        assert pending.id is not None

        # Get
        retrieved = repo.get_pending_authorization("oauth-lifecycle")
        assert retrieved is not None
        assert retrieved.state == "test-state"

        # Update with code
        retrieved.authorization_code = "auth-code"
        repo.update_pending_authorization(retrieved)
        db_session.flush()

        updated = repo.get_pending_authorization("oauth-lifecycle")
        assert updated.authorization_code == "auth-code"

        # Delete
        result = repo.delete_pending_authorization("oauth-lifecycle")
        assert result is True

        # Verify deleted
        assert repo.get_pending_authorization("oauth-lifecycle") is None

    def test_delete_expired_pending_authorizations(self, repo: OAuthRepository, db_session: Session):
        """Test cleanup of expired pending authorizations."""
        # Create old pending authorization (manually set old timestamp)
        pending = repo.create_pending_authorization(
            provider_key="oauth-expired",
            state="old-state",
        )
        db_session.flush()

        # Manually update initiated_at to be old
        pending.initiated_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        repo.update_pending_authorization(pending)
        db_session.flush()

        # Create recent pending authorization
        repo.create_pending_authorization(
            provider_key="oauth-recent",
            state="recent-state",
        )
        db_session.flush()

        # Delete expired (older than 5 minutes)
        deleted_count = repo.delete_expired_pending_authorizations(max_age_seconds=300)

        assert deleted_count == 1
        assert repo.get_pending_authorization("oauth-expired") is None
        assert repo.get_pending_authorization("oauth-recent") is not None


class TestMCPServerRepository:
    """Tests for MCP server repository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> MCPServerRepository:
        return MCPServerRepository(db_session)

    def test_create_stdio_server(self, repo: MCPServerRepository):
        """Test creating a STDIO MCP server config."""
        config = MCPServerConfig(
            name="Local MCP Server",
            server_type=MCPServerType.STDIO,
            config_json=json.dumps({"command": "npx", "args": ["-y", "@mcp/server"]}),
        )

        created = repo.create(config)

        assert created.id is not None
        assert created.name == "Local MCP Server"
        assert created.server_type == MCPServerType.STDIO

        parsed_config = json.loads(created.config_json)
        assert parsed_config["command"] == "npx"

    def test_create_http_server(self, repo: MCPServerRepository):
        """Test creating an HTTP MCP server config."""
        config = MCPServerConfig(
            name="Remote MCP Server",
            server_type=MCPServerType.HTTP,
            config_json=json.dumps(
                {
                    "url": "https://mcp.example.com",
                    "auth_type": "oauth",
                }
            ),
        )

        created = repo.create(config)

        assert created.id is not None
        assert created.server_type == MCPServerType.HTTP

        parsed_config = json.loads(created.config_json)
        assert parsed_config["auth_type"] == "oauth"

    def test_get_all_servers(self, repo: MCPServerRepository, db_session: Session):
        """Test getting all MCP server configs."""
        config1 = MCPServerConfig(
            name="Server A",
            server_type=MCPServerType.STDIO,
            config_json=json.dumps({"command": "cmd1"}),
        )
        config2 = MCPServerConfig(
            name="Server B",
            server_type=MCPServerType.HTTP,
            config_json=json.dumps({"url": "https://example.com"}),
        )

        repo.create(config1)
        repo.create(config2)
        db_session.flush()

        all_servers = repo.get_all()

        assert len(all_servers) == 2
        names = [s.name for s in all_servers]
        assert "Server A" in names
        assert "Server B" in names


class TestOAuthService:
    """Tests for OAuth service."""

    @pytest.fixture
    def oauth_repo(self, db_session: Session) -> OAuthRepository:
        return OAuthRepository(db_session)

    @pytest.fixture
    def service(self, oauth_repo: OAuthRepository) -> OAuthService:
        return OAuthService(oauth_repo)

    def test_generate_provider_keys(self, service: OAuthService):
        """Test provider key generation."""
        oauth_key = service.generate_oauth_provider_key(123)
        assert oauth_key == "oauth-123"

        mcp_key = service.generate_mcp_provider_key(456)
        assert mcp_key == "mcp-456"

    def test_token_expiration_check(self, service: OAuthService, db_session: Session):
        """Test token expiration checking."""
        provider_key = "oauth-expiry-test"

        # No token - should report expired
        assert service.is_token_expired(provider_key) is True

        # Token with future expiry - not expired
        future_expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
        service.store_tokens(
            provider_key,
            TokenData(
                access_token="valid-token",
                expires_at=future_expiry,
            ),
        )
        db_session.flush()
        assert service.is_token_expired(provider_key) is False

        # Token with past expiry - expired
        past_expiry = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        service.store_tokens(
            provider_key,
            TokenData(
                access_token="expired-token",
                expires_at=past_expiry,
            ),
        )
        db_session.flush()
        assert service.is_token_expired(provider_key) is True

    def test_store_and_retrieve_tokens(self, service: OAuthService, db_session: Session):
        """Test storing and retrieving tokens via service."""
        provider_key = "oauth-store-test"

        token_data = TokenData(
            access_token="my-access-token",
            refresh_token="my-refresh-token",
            token_type="Bearer",
            scopes="read write",
        )

        service.store_tokens(provider_key, token_data)
        db_session.flush()

        retrieved = service.get_tokens(provider_key)

        assert retrieved is not None
        assert retrieved.access_token == "my-access-token"
        assert retrieved.refresh_token == "my-refresh-token"
        assert retrieved.scopes == "read write"
