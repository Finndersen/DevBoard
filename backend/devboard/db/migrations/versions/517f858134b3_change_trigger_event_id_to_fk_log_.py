"""change_trigger_event_id_to_fk_log_entries

Revision ID: 517f858134b3
Revises: v2w3x4y5z6a7
Create Date: 2026-05-27 00:37:55.200315

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "517f858134b3"
down_revision: str | Sequence[str] | None = "v2w3x4y5z6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "background_agent_runs",
        "trigger_event_id",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_background_agent_runs_trigger_event_id",
        "background_agent_runs",
        "log_entries",
        ["trigger_event_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_background_agent_runs_trigger_event_id", "background_agent_runs", type_="foreignkey")
    op.alter_column(
        "background_agent_runs",
        "trigger_event_id",
        existing_type=sa.Integer(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=True,
    )
