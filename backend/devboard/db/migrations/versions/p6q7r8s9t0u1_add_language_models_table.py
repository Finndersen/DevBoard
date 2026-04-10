"""language_models branch point

Revision ID: ee1f2a3b4c5d
Revises: 97ddb3744fe6
Create Date: 2026-03-20 10:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "ee1f2a3b4c5d"
down_revision: str | Sequence[str] | None = "97ddb3744fe6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
