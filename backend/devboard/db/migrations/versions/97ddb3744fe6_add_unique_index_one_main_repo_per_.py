"""add unique index one main repo per codebase

Revision ID: 97ddb3744fe6
Revises: 3d50061c552a
Create Date: 2026-03-20 16:29:07.747888

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "97ddb3744fe6"
down_revision: str | Sequence[str] | None = "3d50061c552a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial unique index to enforce one main repo slot per codebase."""
    op.create_index(
        "uq_one_main_repo_per_codebase",
        "worktree_slots",
        ["codebase_id"],
        unique=True,
        sqlite_where=sa.text("is_main_repo = 1"),
    )


def downgrade() -> None:
    """Remove partial unique index."""
    op.drop_index(
        "uq_one_main_repo_per_codebase",
        table_name="worktree_slots",
        sqlite_where=sa.text("is_main_repo = 1"),
    )
