"""merge_all_heads

Revision ID: 256848dbafa3
Revises: 376c405af092, t1u2v3w4x5y6, ff2a3b4c5d6e
Create Date: 2026-04-11 23:03:15.022515

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "256848dbafa3"
down_revision: str | Sequence[str] | None = ("376c405af092", "t1u2v3w4x5y6", "ff2a3b4c5d6e")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
