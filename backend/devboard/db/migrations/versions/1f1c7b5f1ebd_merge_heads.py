"""merge heads

Revision ID: 1f1c7b5f1ebd
Revises: c180425c7c71, w3x4y5z6a7b8
Create Date: 2026-07-02 23:20:24.833222

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "1f1c7b5f1ebd"
down_revision: str | Sequence[str] | None = ("c180425c7c71", "w3x4y5z6a7b8")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
