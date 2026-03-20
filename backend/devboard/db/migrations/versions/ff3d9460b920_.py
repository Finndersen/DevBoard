"""Add entity_type to custom field definitions

Revision ID: ff3d9460b920
Revises: k1l2m3n4o5p6
Create Date: 2026-03-01 01:41:48.865791

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ff3d9460b920"
down_revision: str | Sequence[str] | None = "k1l2m3n4o5p6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite requires batch mode (table recreation) to alter constraints.
    # 1. Add entity_type column (default TASK for existing rows)
    # 2. Replace name-only unique constraint with (name, entity_type) compound unique
    with op.batch_alter_table("custom_field_definitions", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "entity_type",
                sa.Enum("PROJECT", "TASK", "CODEBASE", name="entitytype"),
                nullable=False,
                server_default="TASK",
            )
        )
        batch_op.create_unique_constraint("uq_custom_field_name_entity_type", ["name", "entity_type"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("custom_field_definitions", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_custom_field_name_entity_type", type_="unique")
        batch_op.drop_column("entity_type")
        batch_op.create_unique_constraint("uq_custom_field_name", ["name"])
