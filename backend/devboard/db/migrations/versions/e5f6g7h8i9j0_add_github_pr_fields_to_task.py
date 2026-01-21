"""Add GitHub PR fields to Task model

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2025-01-22 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: str | Sequence[str] | None = "d4e5f6g7h8i9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add GitHub PR number to tasks table."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("github_pr_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove GitHub PR number from tasks table."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("github_pr_number")
