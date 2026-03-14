"""add custom_fields to projects

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "l2m3n4o5p6q7"
down_revision: str | Sequence[str] | None = "k1l2m3n4o5p6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add custom_fields JSON column to projects table."""
    op.add_column("projects", sa.Column("custom_fields", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Drop custom_fields column from projects table."""
    op.drop_column("projects", "custom_fields")
