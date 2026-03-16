"""add_claude_project_path_cache

Revision ID: n4o5p6q7r8s9
Revises: b37941949c5f
Create Date: 2026-03-16 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "n4o5p6q7r8s9"
down_revision: str | Sequence[str] | None = "b37941949c5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "claude_project_path_cache",
        sa.Column("encoded_path", sa.String(length=512), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("encoded_path"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("claude_project_path_cache")
