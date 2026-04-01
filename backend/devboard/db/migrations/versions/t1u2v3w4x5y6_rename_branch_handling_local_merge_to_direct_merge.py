"""rename branch_handling local_merge to direct_merge

Revision ID: t1u2v3w4x5y6
Revises: s9t0u1v2w3x4
Create Date: 2026-04-01 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "t1u2v3w4x5y6"
down_revision: str | Sequence[str] | None = "s9t0u1v2w3x4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE codebases SET branch_handling = 'direct_merge' WHERE branch_handling = 'local_merge'")


def downgrade() -> None:
    op.execute("UPDATE codebases SET branch_handling = 'local_merge' WHERE branch_handling = 'direct_merge'")
