"""add_last_activity_at_to_conversations

Revision ID: a2b3c4d5e6f7
Revises: c24bd7de48cc
Create Date: 2026-03-14 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "c24bd7de48cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add last_activity_at column and backfill from message timestamps."""
    op.add_column("conversations", sa.Column("last_activity_at", sa.DateTime(), nullable=True))

    # Backfill: set last_activity_at to MAX(timestamp) of messages, falling back to created_at
    op.execute(
        """
        UPDATE conversations
        SET last_activity_at = COALESCE(
            (SELECT MAX(timestamp) FROM conversation_messages WHERE conversation_messages.conversation_id = conversations.id),
            conversations.created_at
        )
        """
    )


def downgrade() -> None:
    """Remove last_activity_at column."""
    op.drop_column("conversations", "last_activity_at")
