"""add title to conversations

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-03-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m3n4o5p6q7r8"
down_revision: str | Sequence[str] | None = "l2m3n4o5p6q7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add title column to conversations table."""
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(sa.Column("title", sa.String(200), nullable=True))


def downgrade() -> None:
    """Drop title column from conversations table."""
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_column("title")
