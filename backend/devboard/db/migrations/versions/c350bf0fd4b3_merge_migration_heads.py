"""merge migration heads

Revision ID: c350bf0fd4b3
Revises: b484b5145946, db22f2b8cfc8
Create Date: 2025-11-25 01:16:02.210190

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "c350bf0fd4b3"
down_revision: str | Sequence[str] | None = ("b484b5145946", "db22f2b8cfc8")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
