"""add updated_at to tasks

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-03-16 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "o5p6q7r8s9t0"
down_revision: str | Sequence[str] | None = "n4o5p6q7r8s9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add updated_at column to tasks table, backfilling from created_at."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE tasks SET updated_at = created_at")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("updated_at", nullable=False)


def downgrade() -> None:
    """Drop updated_at column from tasks table."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("updated_at")
