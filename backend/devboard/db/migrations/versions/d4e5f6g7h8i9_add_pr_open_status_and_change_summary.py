"""Add PR_OPEN status and change_summary document

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6g7h8i9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add PR_OPEN to TaskStatus enum, CHANGE_SUMMARY to DocumentType enum, and change_summary_id to tasks."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    # PostgreSQL requires altering the enum type directly
    # SQLite stores enums as strings, so no alter needed
    if dialect == "postgresql":
        op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'pr_open'")
        op.execute("ALTER TYPE documenttype ADD VALUE IF NOT EXISTS 'change_summary'")

    # Add change_summary_id column to tasks table
    # Use batch mode for SQLite compatibility (required for adding FK constraints)
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("change_summary_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_tasks_change_summary_id", "documents", ["change_summary_id"], ["id"])


def downgrade() -> None:
    """Remove change_summary_id column from tasks.

    Note: PostgreSQL does not support removing values from enum types,
    so PR_OPEN and CHANGE_SUMMARY values remain in the enum types.
    """
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_change_summary_id", type_="foreignkey")
        batch_op.drop_column("change_summary_id")
