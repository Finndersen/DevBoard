"""Add merge_strategy to codebase

Revision ID: a1b2c3d4e5f6
Revises: db22f2b8cfc8
Create Date: 2025-01-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "db22f2b8cfc8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add merge_strategy column to codebases table."""
    op.add_column(
        "codebases", sa.Column("merge_strategy", sa.String(length=50), nullable=False, server_default="squash")
    )


def downgrade() -> None:
    """Remove merge_strategy column from codebases table."""
    op.drop_column("codebases", "merge_strategy")
