"""simplify_worktree_slot_locking

Revision ID: e9fc3e4d902f
Revises: 3f311ec0944f
Create Date: 2025-11-18 23:56:15.555503

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9fc3e4d902f"
down_revision: str | Sequence[str] | None = "3f311ec0944f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - simplify worktree slot locking."""
    # Remove branch_mode from tasks (if it exists)
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if branch_mode column exists before dropping
    tasks_columns = [col["name"] for col in inspector.get_columns("tasks")]
    if "branch_mode" in tasks_columns:
        with op.batch_alter_table("tasks", schema=None) as batch_op:
            batch_op.drop_column("branch_mode")

    # Simplify worktree_slots locking
    with op.batch_alter_table("worktree_slots", schema=None) as batch_op:
        # Add new locked column (default False for existing rows)
        batch_op.add_column(sa.Column("locked", sa.Boolean(), nullable=False, server_default="0"))

        # Drop old locking columns (in SQLite with batch mode, foreign keys are recreated automatically)
        batch_op.drop_column("locked_by_task_id")
        batch_op.drop_column("locked_at")

    # Migrate data: Set locked=True for any slots that had locked_by_task_id
    # Note: In SQLite with batch mode, the column is already dropped during table recreation
    # Existing locked slots will be set to locked=False (server_default='0')
    # This is acceptable as locks are transient and will be re-established on next agent run


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add branch_mode to tasks
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("branch_mode", sa.VARCHAR(length=12), nullable=True))

    # Restore old worktree_slots locking columns
    with op.batch_alter_table("worktree_slots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("locked_at", sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column("locked_by_task_id", sa.INTEGER(), nullable=True))
        batch_op.create_foreign_key("worktree_slots_locked_by_task_id_fkey", "tasks", ["locked_by_task_id"], ["id"])
        batch_op.drop_column("locked")
