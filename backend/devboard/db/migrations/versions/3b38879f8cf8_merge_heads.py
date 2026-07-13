"""merge heads

Revision ID: 3b38879f8cf8
Revises: 1f1c7b5f1ebd, x4y5z6a7b8c9
Create Date: 2026-07-13 21:08:09.988524

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "3b38879f8cf8"
down_revision: str | Sequence[str] | None = ("1f1c7b5f1ebd", "x4y5z6a7b8c9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
