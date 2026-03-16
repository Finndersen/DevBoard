"""add cascade delete to implementation_plans task_id fk

Revision ID: n4o5p6q7r8s9
Revises: b37941949c5f
Create Date: 2026-03-16 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "n4o5p6q7r8s9"
down_revision: str | Sequence[str] | None = "b37941949c5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ON DELETE CASCADE to implementation_plans.task_id FK.

    SQLite doesn't support ALTER TABLE for FK changes; the existing FK and UNIQUE
    constraints are unnamed, so we recreate the table using raw SQL.
    """
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
    """Remove ON DELETE CASCADE from implementation_plans.task_id FK."""
    op.execute("""
        CREATE TABLE implementation_plans_new (
            id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            overview TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (task_id),
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    """)
    op.execute("INSERT INTO implementation_plans_new SELECT * FROM implementation_plans")
    op.execute("DROP TABLE implementation_plans")
    op.execute("ALTER TABLE implementation_plans_new RENAME TO implementation_plans")
