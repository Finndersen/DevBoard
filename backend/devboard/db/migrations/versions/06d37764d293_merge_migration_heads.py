"""merge_migration_heads

Revision ID: 06d37764d293
Revises: ff283b3fbd23, h8i9j0k1l2m3
Create Date: 2026-02-05 17:15:05.637851

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "06d37764d293"
down_revision: str | Sequence[str] | None = ("ff283b3fbd23", "h8i9j0k1l2m3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
