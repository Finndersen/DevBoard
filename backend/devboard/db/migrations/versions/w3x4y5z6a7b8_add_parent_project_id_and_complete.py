"""add parent_project_id and complete to projects

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-07-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "w3x4y5z6a7b8"
down_revision: str | Sequence[str] | None = "v2w3x4y5z6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add parent_project_id (nullable self-FK) and complete (bool) columns to projects."""
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("parent_project_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("complete", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_foreign_key(
            "fk_projects_parent_project_id",
            "projects",
            ["parent_project_id"],
            ["id"],
        )


def downgrade() -> None:
    """Remove parent_project_id and complete columns from projects."""
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_parent_project_id", type_="foreignkey")
        batch_op.drop_column("complete")
        batch_op.drop_column("parent_project_id")
