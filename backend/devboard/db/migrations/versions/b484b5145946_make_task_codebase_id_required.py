"""Make Task.codebase_id required

Revision ID: b484b5145946
Revises: e9fc3e4d902f
Create Date: 2025-11-19 23:46:48.821442

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b484b5145946"
down_revision: str | Sequence[str] | None = "e9fc3e4d902f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support ALTER COLUMN, so use batch operations
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.alter_column("codebase_id", existing_type=sa.INTEGER(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # SQLite doesn't support ALTER COLUMN, so use batch operations
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.alter_column("codebase_id", existing_type=sa.INTEGER(), nullable=True)
