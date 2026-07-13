"""add initiatives table and initiative_id to tasks

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-07-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "x4y5z6a7b8c9"
down_revision: str | Sequence[str] | None = "w3x4y5z6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initiatives table, add initiative_id to tasks, drop parent_project_id from projects."""
    # 1. Create initiatives table
    op.create_table(
        "initiatives",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("specification_document_id", sa.Integer(), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["specification_document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Add initiative_id column to tasks table
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("initiative_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_initiative_id",
            "initiatives",
            ["initiative_id"],
            ["id"],
        )

    # 3. Drop parent_project_id from projects table
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("fk_projects_parent_project_id", type_="foreignkey")
        batch_op.drop_column("parent_project_id")


def downgrade() -> None:
    """Reverse: drop initiatives table, remove initiative_id from tasks, restore parent_project_id."""
    # Restore parent_project_id to projects
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("parent_project_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_parent_project_id",
            "projects",
            ["parent_project_id"],
            ["id"],
        )

    # Remove initiative_id from tasks
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_initiative_id", type_="foreignkey")
        batch_op.drop_column("initiative_id")

    # Drop initiatives table
    op.drop_table("initiatives")
