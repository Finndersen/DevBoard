"""make branch_name non-nullable and drop remote_task_id

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-02-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: str | Sequence[str] | None = "j0k1l2m3n4o5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill NULL branch_name values and make non-nullable, drop remote_task_id."""
    # Backfill NULL branch_name values to empty string
    op.execute("UPDATE tasks SET branch_name = '' WHERE branch_name IS NULL")

    with op.batch_alter_table("tasks") as batch_op:
        # Make branch_name non-nullable (backfill above handles legacy NULLs)
        batch_op.alter_column(
            "branch_name",
            existing_type=sa.String(255),
            nullable=False,
        )
        # Drop remote_task_id column
        batch_op.drop_column("remote_task_id")


def downgrade() -> None:
    """Restore remote_task_id column and make branch_name nullable again."""
    with op.batch_alter_table("tasks") as batch_op:
        # Make branch_name nullable again and remove server default
        batch_op.alter_column(
            "branch_name",
            existing_type=sa.String(255),
            nullable=True,
            server_default=None,
        )
        # Re-add remote_task_id column
        batch_op.add_column(sa.Column("remote_task_id", sa.String(100), nullable=True))
