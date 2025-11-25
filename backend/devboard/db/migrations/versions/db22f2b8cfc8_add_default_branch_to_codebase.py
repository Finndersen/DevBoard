"""Add default_branch to codebase

Revision ID: db22f2b8cfc8
Revises: 0e6f210b42b8
Create Date: 2025-01-15 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "db22f2b8cfc8"
down_revision: str | Sequence[str] | None = "0e6f210b42b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add default_branch column to codebases table."""
    op.add_column(
        "codebases", sa.Column("default_branch", sa.String(length=255), nullable=False, server_default="origin/main")
    )


def downgrade() -> None:
    """Remove default_branch column from codebases table."""
    op.drop_column("codebases", "default_branch")
