"""Add custom_field_definitions table and custom_fields column to tasks

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2025-01-29 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7h8i9j0k1l2"
down_revision: str | Sequence[str] | None = "f6g7h8i9j0k1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create custom_field_definitions table and add custom_fields to tasks."""
    # Create custom_field_definitions table
    op.create_table(
        "custom_field_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "type",
            sa.Enum("text", "boolean", "enum", name="customfieldtype"),
            nullable=False,
        ),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Add custom_fields JSON column to tasks table
    op.add_column("tasks", sa.Column("custom_fields", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove custom_fields from tasks and drop custom_field_definitions table."""
    # Remove custom_fields column from tasks
    op.drop_column("tasks", "custom_fields")

    # Drop custom_field_definitions table
    op.drop_table("custom_field_definitions")

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS customfieldtype")
