"""Add developer_context to codebase

Revision ID: p6q7r8s9t0u1
Revises: 97ddb3744fe6
Create Date: 2026-03-20 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p6q7r8s9t0u1"
down_revision: str | Sequence[str] | None = "97ddb3744fe6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add developer_context column to codebases table."""
    op.add_column("codebases", sa.Column("developer_context", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove developer_context column from codebases table."""
    op.drop_column("codebases", "developer_context")
