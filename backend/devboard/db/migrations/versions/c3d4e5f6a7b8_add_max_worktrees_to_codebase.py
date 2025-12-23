"""Add max_worktrees to codebase

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2025-01-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add max_worktrees column to codebases table."""
    op.add_column("codebases", sa.Column("max_worktrees", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove max_worktrees column from codebases table."""
    op.drop_column("codebases", "max_worktrees")
