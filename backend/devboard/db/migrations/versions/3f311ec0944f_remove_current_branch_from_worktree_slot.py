"""remove_current_branch_from_worktree_slot

Revision ID: 3f311ec0944f
Revises: d8b6f627c9c5
Create Date: 2025-11-15 00:31:43.517032

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f311ec0944f"
down_revision: str | Sequence[str] | None = "d8b6f627c9c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Remove current_branch column from worktree_slots
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table("worktree_slots", schema=None) as batch_op:
        batch_op.drop_column("current_branch")


def downgrade() -> None:
    """Downgrade schema."""
    # Add current_branch column back
    with op.batch_alter_table("worktree_slots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("current_branch", sa.String(255), nullable=True))
