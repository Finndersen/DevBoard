"""add model_type to implementation_steps

Revision ID: v2w3x4y5z6a7
Revises: u2v3w4x5y6z7
Create Date: 2026-04-16 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "v2w3x4y5z6a7"
down_revision: str | Sequence[str] | None = "u2v3w4x5y6z7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable model_type column to implementation_steps table."""
    with op.batch_alter_table("implementation_steps") as batch_op:
        batch_op.add_column(sa.Column("model_type", sa.String(), nullable=True))


def downgrade() -> None:
    """Drop model_type column from implementation_steps table."""
    with op.batch_alter_table("implementation_steps") as batch_op:
        batch_op.drop_column("model_type")
