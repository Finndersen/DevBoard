"""Add git branch and worktree management

Revision ID: d8b6f627c9c5
Revises: bc33326dcc47
Create Date: 2025-11-14 19:07:24.074396

"""

# revision identifiers, used by Alembic.
revision: str = "d8b6f627c9c5"
down_revision: str | list[str] | None = "bc33326dcc47"
branch_labels: str | list[str] | None = None
depends_on: str | list[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Note: All operations in this migration (worktree_slots table and git branch fields)
    # were already created in migration bc33326dcc47
    pass


def downgrade() -> None:
    """Downgrade schema."""
    # Note: All operations handled in migration bc33326dcc47
    pass
