"""merge_heads

Revision ID: 4a89cffd93d5
Revises: q7r8s9t0u1v2, s9t0u1v2w3x4
Create Date: 2026-03-23 13:43:59.885725

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "4a89cffd93d5"
down_revision: str | Sequence[str] | None = ("q7r8s9t0u1v2", "s9t0u1v2w3x4")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
