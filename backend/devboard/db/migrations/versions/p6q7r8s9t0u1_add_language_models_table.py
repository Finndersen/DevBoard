"""add language_models table

Revision ID: ee1f2a3b4c5d
Revises: 97ddb3744fe6
Create Date: 2026-03-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ee1f2a3b4c5d"
down_revision: str | Sequence[str] | None = "97ddb3744fe6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "language_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.Enum("openai", "anthropic", "google", name="llmprovider"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("model_type", sa.Enum("fast", "standard", "advanced", name="modeltype"), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("bedrock_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "name", name="uq_language_model_provider_name"),
    )


def downgrade() -> None:
    op.drop_table("language_models")
    op.execute("DROP TYPE IF EXISTS llmprovider")
    op.execute("DROP TYPE IF EXISTS modeltype")
