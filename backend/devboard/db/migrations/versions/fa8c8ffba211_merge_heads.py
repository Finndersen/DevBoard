"""merge_heads

Revision ID: fa8c8ffba211
Revises: p6q7r8s9t0u1, r8s9t0u1v2w3
Create Date: 2026-03-21 05:28:28.629470

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "fa8c8ffba211"
down_revision: str | Sequence[str] | None = ("p6q7r8s9t0u1", "r8s9t0u1v2w3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
