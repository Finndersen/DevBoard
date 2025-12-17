"""Add OAuth tables

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2025-01-21 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add OAuth-related tables."""
    # MCP Server Configs table
    op.create_table(
        "mcp_server_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "server_type",
            sa.Enum("stdio", "http", name="mcpservertype"),
            nullable=False,
        ),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # OAuth Providers table
    op.create_table(
        "oauth_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "provider_type",
            sa.Enum("jira", "slack", "github", name="oauthprovidertype"),
            nullable=False,
        ),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret", sa.String(length=512), nullable=False),
        sa.Column("authorization_url", sa.String(length=1024), nullable=False),
        sa.Column("token_url", sa.String(length=1024), nullable=False),
        sa.Column("scopes", sa.String(length=1024), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # OAuth Tokens table
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(length=255), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("scopes", sa.String(length=1024), nullable=True),
        sa.Column("raw_token_response", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key"),
    )

    # OAuth Client Info table
    op.create_table(
        "oauth_client_info",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(length=255), nullable=False),
        sa.Column("raw_client_info", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key"),
    )

    # Pending OAuth Authorizations table
    op.create_table(
        "pending_oauth_authorizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("code_verifier", sa.String(length=255), nullable=True),
        sa.Column("redirect_uri", sa.String(length=1024), nullable=True),
        sa.Column("authorization_code", sa.Text(), nullable=True),
        sa.Column("initiated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key"),
    )


def downgrade() -> None:
    """Remove OAuth-related tables."""
    op.drop_table("pending_oauth_authorizations")
    op.drop_table("oauth_client_info")
    op.drop_table("oauth_tokens")
    op.drop_table("oauth_providers")
    op.drop_table("mcp_server_configs")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS mcpservertype")
    op.execute("DROP TYPE IF EXISTS oauthprovidertype")
