"""add unique constraint implementation step number

Revision ID: u2v3w4x5y6z7
Revises: 256848dbafa3
Create Date: 2026-04-12 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "u2v3w4x5y6z7"
down_revision: str | Sequence[str] | None = "256848dbafa3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(__import__("sqlalchemy").text("DROP TABLE IF EXISTS _alembic_tmp_implementation_steps"))
    conn.execute(
        __import__("sqlalchemy").text(
            """
            DELETE FROM implementation_steps
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM implementation_steps
                GROUP BY implementation_plan_id, step_number
            )
            """
        )
    )
    with op.batch_alter_table("implementation_steps") as batch_op:
        batch_op.create_unique_constraint(
            "uq_implementation_step_number",
            ["implementation_plan_id", "step_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("implementation_steps") as batch_op:
        batch_op.drop_constraint(
            "uq_implementation_step_number",
            type_="unique",
        )
