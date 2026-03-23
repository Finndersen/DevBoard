"""add conversation_id to implementation_steps

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-03-21 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p6q7r8s9t0u1"
down_revision: str | Sequence[str] | None = "o5p6q7r8s9t0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable conversation_id column to implementation_steps table."""
    with op.batch_alter_table("implementation_steps") as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Drop conversation_id column from implementation_steps table."""
    with op.batch_alter_table("implementation_steps") as batch_op:
        batch_op.drop_column("conversation_id")
