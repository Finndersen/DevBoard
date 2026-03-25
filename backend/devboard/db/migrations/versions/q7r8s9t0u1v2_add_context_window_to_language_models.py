"""add context_window to language_models

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-03-20 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "q7r8s9t0u1v2"
down_revision: str | Sequence[str] | None = "r7s8t9u0v1w2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add context_window column to language_models table."""
    op.add_column("language_models", sa.Column("context_window", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove context_window column from language_models table."""
    op.drop_column("language_models", "context_window")
