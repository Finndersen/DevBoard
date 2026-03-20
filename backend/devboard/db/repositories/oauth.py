"""OAuth repository for OAuth-related data access operations."""

import datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult

from devboard.db.models import OAuthClientInfo, OAuthProvider, OAuthToken, PendingOAuthAuthorization
from devboard.db.repositories.base import BaseRepository


class OAuthRepository(BaseRepository[OAuthProvider]):
    """Repository for OAuth-related data access operations."""

    # OAuth Provider operations

    def get_oauth_provider(self, provider_id: int) -> OAuthProvider | None:
        stmt = select(OAuthProvider).where(OAuthProvider.id == provider_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_oauth_providers(self) -> list[OAuthProvider]:
        stmt = select(OAuthProvider).order_by(OAuthProvider.name)
        return list(self.db.execute(stmt).scalars().all())

    def create_oauth_provider(self, provider: OAuthProvider) -> OAuthProvider:
        self.db.add(provider)
        self.db.flush()
        return provider

    def update_oauth_provider(self, provider: OAuthProvider) -> OAuthProvider:
        self.db.merge(provider)
        self.db.flush()
        return provider

    def delete_oauth_provider(self, provider_id: int) -> bool:
        provider = self.get_oauth_provider(provider_id)
        if provider:
            self.db.delete(provider)
            self.db.flush()
            return True
        return False

    # OAuth Token operations

    def get_token_by_provider_key(self, provider_key: str) -> OAuthToken | None:
        stmt = select(OAuthToken).where(OAuthToken.provider_key == provider_key)
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert_token(
        self,
        provider_key: str,
        access_token: str,
        refresh_token: str | None = None,
        token_type: str = "Bearer",
        expires_at: datetime.datetime | None = None,
        scopes: str | None = None,
        raw_token_response: str | None = None,
    ) -> OAuthToken:
        """Create or update an OAuth token."""
        existing = self.get_token_by_provider_key(provider_key)

        if existing:
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.token_type = token_type
            existing.expires_at = expires_at
            existing.scopes = scopes
            existing.raw_token_response = raw_token_response
            self.db.flush()
            return existing
        else:
            token = OAuthToken(
                provider_key=provider_key,
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                expires_at=expires_at,
                scopes=scopes,
                raw_token_response=raw_token_response,
            )
            self.db.add(token)
            self.db.flush()
            return token

    def delete_token(self, provider_key: str) -> bool:
        token = self.get_token_by_provider_key(provider_key)
        if token:
            self.db.delete(token)
            self.db.flush()
            return True
        return False

    # OAuth Client Info operations

    def get_client_info_by_provider_key(self, provider_key: str) -> OAuthClientInfo | None:
        stmt = select(OAuthClientInfo).where(OAuthClientInfo.provider_key == provider_key)
        return self.db.execute(stmt).scalar_one_or_none()

    def upsert_client_info(self, provider_key: str, raw_client_info: str) -> OAuthClientInfo:
        """Create or update OAuth client info."""
        existing = self.get_client_info_by_provider_key(provider_key)

        if existing:
            existing.raw_client_info = raw_client_info
            self.db.flush()
            return existing
        else:
            client_info = OAuthClientInfo(
                provider_key=provider_key,
                raw_client_info=raw_client_info,
            )
            self.db.add(client_info)
            self.db.flush()
            return client_info

    def delete_client_info(self, provider_key: str) -> bool:
        client_info = self.get_client_info_by_provider_key(provider_key)
        if client_info:
            self.db.delete(client_info)
            self.db.flush()
            return True
        return False

    # Pending OAuth Authorization operations

    def get_pending_authorization(self, provider_key: str) -> PendingOAuthAuthorization | None:
        stmt = select(PendingOAuthAuthorization).where(PendingOAuthAuthorization.provider_key == provider_key)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_pending_authorization(
        self,
        provider_key: str,
        state: str | None = None,
        code_verifier: str | None = None,
        redirect_uri: str | None = None,
    ) -> PendingOAuthAuthorization:
        """Create a new pending OAuth authorization.

        Only one pending authorization per provider_key is allowed.
        If one exists, it will be deleted first.
        """
        # Delete any existing pending authorization for this provider
        self.delete_pending_authorization(provider_key)

        pending = PendingOAuthAuthorization(
            provider_key=provider_key,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        )
        self.db.add(pending)
        self.db.flush()
        return pending

    def update_pending_authorization(self, pending: PendingOAuthAuthorization) -> PendingOAuthAuthorization:
        self.db.merge(pending)
        self.db.flush()
        return pending

    def delete_pending_authorization(self, provider_key: str) -> bool:
        pending = self.get_pending_authorization(provider_key)
        if pending:
            self.db.delete(pending)
            self.db.flush()
            return True
        return False

    def delete_expired_pending_authorizations(self, max_age_seconds: int = 600) -> int:
        """Delete pending authorizations older than the specified age (default: 10 minutes)."""
        cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=max_age_seconds)
        stmt = delete(PendingOAuthAuthorization).where(PendingOAuthAuthorization.initiated_at < cutoff)
        result = self.db.execute(stmt)
        self.db.flush()
        return cast(CursorResult[Any], result).rowcount
