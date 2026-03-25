"""add language_models table

Revision ID: r7s8t9u0v1w2
Revises: p6q7r8s9t0u1
Create Date: 2026-03-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r7s8t9u0v1w2"
down_revision: str | Sequence[str] | None = ("p6q7r8s9t0u1", "r8s9t0u1v2w3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create language_models table."""
    op.create_table(
        "language_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("openai", "anthropic", "google", name="llmprovider"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "model_type",
            sa.Enum("fast", "standard", "advanced", name="modeltype"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("bedrock_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "name", name="uq_language_model_provider_name"),
    )


def downgrade() -> None:
    """Drop language_models table."""
    op.drop_table("language_models")
    op.execute("DROP TYPE IF EXISTS llmprovider")
    op.execute("DROP TYPE IF EXISTS modeltype")
