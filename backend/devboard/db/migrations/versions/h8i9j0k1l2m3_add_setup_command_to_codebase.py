"""Add setup_command to codebase

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2025-02-05 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: str | Sequence[str] | None = "g7h8i9j0k1l2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add setup_command column to codebases table."""
    op.add_column("codebases", sa.Column("setup_command", sa.String(1024), nullable=True))


def downgrade() -> None:
    """Remove setup_command column from codebases table."""
    op.drop_column("codebases", "setup_command")
