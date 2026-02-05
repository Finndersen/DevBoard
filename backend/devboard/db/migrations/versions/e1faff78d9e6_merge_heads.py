"""merge_heads

Revision ID: e1faff78d9e6
Revises: d4e5f6a7b8c9, g7h8i9j0k1l2
Create Date: 2026-02-05 10:50:27.250118

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e1faff78d9e6"
down_revision: str | Sequence[str] | None = ("d4e5f6a7b8c9", "g7h8i9j0k1l2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
