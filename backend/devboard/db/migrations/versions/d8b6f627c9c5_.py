"""Add git branch and worktree management

Revision ID: d8b6f627c9c5
Revises: bc33326dcc47
Create Date: 2025-11-14 19:07:24.074396

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8b6f627c9c5"
down_revision: str | Sequence[str] | None = "bc33326dcc47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create worktree_slots table
    op.create_table(
        "worktree_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codebase_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("is_main_repo", sa.Boolean(), nullable=False),
        sa.Column("locked_by_task_id", sa.Integer(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("current_branch", sa.String(length=255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_by_task_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["codebase_id"],
            ["codebases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["locked_by_task_id"],
            ["tasks.id"],
        ),
        sa.ForeignKeyConstraint(
            ["last_used_by_task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add git branch fields to tasks table
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("branch_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("base_branch", sa.String(length=255), nullable=False, server_default="main"))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove git branch fields from tasks table
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("base_branch")
        batch_op.drop_column("branch_name")

    # Drop worktree_slots table
    op.drop_table("worktree_slots")
