"""merge_heads

Revision ID: dee81c394adb
Revises: 92a301a7ba1c, m3n4o5p6q7r8
Create Date: 2026-03-16 01:25:16.717734

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "dee81c394adb"
down_revision: str | Sequence[str] | None = ("92a301a7ba1c", "m3n4o5p6q7r8")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
