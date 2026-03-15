"""merge_heads

Revision ID: 92a301a7ba1c
Revises: a2b3c4d5e6f7, l2m3n4o5p6q7
Create Date: 2026-03-14 12:34:58.128406

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "92a301a7ba1c"
down_revision: str | Sequence[str] | None = ("a2b3c4d5e6f7", "l2m3n4o5p6q7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
