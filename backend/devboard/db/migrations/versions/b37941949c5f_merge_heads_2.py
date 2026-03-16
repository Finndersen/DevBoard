"""merge_heads_2

Revision ID: b37941949c5f
Revises: a768e20f32e8, dee81c394adb
Create Date: 2026-03-16 01:30:02.297550

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b37941949c5f"
down_revision: str | Sequence[str] | None = ("a768e20f32e8", "dee81c394adb")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
