"""merge branches for language_models (table already created by prior migration)

Revision ID: r7s8t9u0v1w2
Revises: ee1f2a3b4c5d, r8s9t0u1v2w3
Create Date: 2026-03-20 10:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "r7s8t9u0v1w2"
down_revision: str | Sequence[str] | None = ("ee1f2a3b4c5d", "r8s9t0u1v2w3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
