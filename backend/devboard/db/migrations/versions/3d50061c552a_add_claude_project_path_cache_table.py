"""add_claude_project_path_cache_table

Revision ID: 3d50061c552a
Revises: b4f37f3b21d5
Create Date: 2026-03-17 00:58:12.432025

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "3d50061c552a"
down_revision: str | Sequence[str] | None = "b4f37f3b21d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # Create the table only if it was lost due to the duplicate-revision cleanup.
    # On fresh installs this will always run; on existing dev DBs the table already exists.
    if not inspect(bind).has_table("claude_project_path_cache"):
        op.create_table(
            "claude_project_path_cache",
            sa.Column("encoded_path", sa.String(length=512), nullable=False),
            sa.Column("path", sa.String(length=1024), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("encoded_path"),
        )

    # Add ON DELETE CASCADE to implementation_plans.task_id FK.
    # SQLite doesn't support ALTER TABLE for FK changes, so recreate the table.
    # Skip if it was already applied (fresh DB ran n4o5p6q7r8s9 which includes CASCADE).
    fk_list = inspect(bind).get_foreign_keys("implementation_plans")
    has_cascade = any(
        fk.get("referred_table") == "tasks" and fk.get("options", {}).get("ondelete") == "CASCADE" for fk in fk_list
    )
    if not has_cascade:
        op.execute("""
            CREATE TABLE implementation_plans_new (
                id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                overview TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE (task_id),
                FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
            )
        """)
        op.execute("INSERT INTO implementation_plans_new SELECT * FROM implementation_plans")
        op.execute("DROP TABLE implementation_plans")
        op.execute("ALTER TABLE implementation_plans_new RENAME TO implementation_plans")


def downgrade() -> None:
    op.drop_table("claude_project_path_cache")
