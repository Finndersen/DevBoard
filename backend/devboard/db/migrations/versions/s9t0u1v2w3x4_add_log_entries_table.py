"""add log_entries table

Revision ID: s9t0u1v2w3x4
Revises: fa8c8ffba211
Create Date: 2026-03-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "s9t0u1v2w3x4"
down_revision: str | Sequence[str] | None = "fa8c8ffba211"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the log_entries table."""
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("developer", "system", "agent", name="logentrysource"),
            nullable=False,
        ),
        sa.Column("type", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "resolved", "superseded", name="logentrystatus"),
            nullable=False,
        ),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_log_entries_project_id", "log_entries", ["project_id"])
    op.create_index("ix_log_entries_task_id", "log_entries", ["task_id"])
    op.create_index("ix_log_entries_timestamp", "log_entries", ["timestamp"])
    op.create_index("ix_log_entries_type", "log_entries", ["type"])


def downgrade() -> None:
    """Drop the log_entries table."""
    op.drop_index("ix_log_entries_type", table_name="log_entries")
    op.drop_index("ix_log_entries_timestamp", table_name="log_entries")
    op.drop_index("ix_log_entries_task_id", table_name="log_entries")
    op.drop_index("ix_log_entries_project_id", table_name="log_entries")
    op.drop_table("log_entries")
    op.execute("DROP TYPE IF EXISTS logentrysource")
    op.execute("DROP TYPE IF EXISTS logentrystatus")
