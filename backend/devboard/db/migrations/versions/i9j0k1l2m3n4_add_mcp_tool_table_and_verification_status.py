"""add_mcp_tool_table_and_verification_status

Revision ID: i9j0k1l2m3n4
Revises: 06d37764d293
Create Date: 2026-02-05 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: str | Sequence[str] | None = "06d37764d293"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add verification status fields to mcp_server_configs
    with op.batch_alter_table("mcp_server_configs") as batch_op:
        batch_op.add_column(sa.Column("last_verified_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_verified_success", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("last_verified_error", sa.Text(), nullable=True))

    # Create mcp_tools table
    op.create_table(
        "mcp_tools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_schema", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["mcp_server_configs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("server_id", "name", name="uq_mcp_tool_server_name"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop mcp_tools table
    op.drop_table("mcp_tools")

    # Remove verification status fields from mcp_server_configs
    with op.batch_alter_table("mcp_server_configs") as batch_op:
        batch_op.drop_column("last_verified_error")
        batch_op.drop_column("last_verified_success")
        batch_op.drop_column("last_verified_at")
