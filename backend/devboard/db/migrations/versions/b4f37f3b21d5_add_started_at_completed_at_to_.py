"""add_started_at_completed_at_to_implementation_steps

Revision ID: b4f37f3b21d5
Revises: o5p6q7r8s9t0
Create Date: 2026-03-16 23:58:44.526383

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4f37f3b21d5"
down_revision: str | Sequence[str] | None = "o5p6q7r8s9t0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add started_at and completed_at columns to implementation_steps."""
    op.add_column("implementation_steps", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("implementation_steps", sa.Column("completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove started_at and completed_at columns from implementation_steps."""
    op.drop_column("implementation_steps", "completed_at")
    op.drop_column("implementation_steps", "started_at")
