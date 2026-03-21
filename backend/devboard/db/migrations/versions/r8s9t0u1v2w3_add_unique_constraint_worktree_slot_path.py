"""add unique constraint worktree slot path

Revision ID: r8s9t0u1v2w3
Revises: o5p6q7r8s9t0
Create Date: 2026-03-20 17:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "r8s9t0u1v2w3"
down_revision: str | Sequence[str] | None = "97ddb3744fe6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_worktree_slot_path",
        "worktree_slots",
        ["path"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_worktree_slot_path", table_name="worktree_slots")
