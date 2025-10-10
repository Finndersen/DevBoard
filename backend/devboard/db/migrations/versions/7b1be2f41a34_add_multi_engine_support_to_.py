"""add_multi_engine_support_to_conversations

Revision ID: 7b1be2f41a34
Revises: ebb66080d9c0
Create Date: 2025-10-09 16:49:45.125564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b1be2f41a34'
down_revision: Union[str, Sequence[str], None] = 'ebb66080d9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns first (outside batch mode to avoid circular dependency)
    op.add_column('conversations', sa.Column('engine', sa.String(), nullable=False, server_default='internal'))
    op.add_column('conversations', sa.Column('external_session_id', sa.String(), nullable=True))
    op.add_column('conversations', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('conversations', sa.Column('archived_at', sa.DateTime(), nullable=True))

    # SQLite requires batch mode for constraint operations
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        # Drop the unique constraint
        batch_op.drop_constraint('uq_one_conversation_per_entity', type_='unique')

        # Add index for efficiently querying active conversations
        batch_op.create_index(
            'idx_active_conversations',
            ['parent_entity_type', 'parent_entity_id', 'is_active']
        )


def downgrade() -> None:
    """Downgrade schema."""
    # SQLite requires batch mode for constraint operations
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        # Drop the index
        batch_op.drop_index('idx_active_conversations')

        # Re-create the unique constraint
        batch_op.create_unique_constraint(
            'uq_one_conversation_per_entity',
            ['parent_entity_type', 'parent_entity_id', 'parent_conversation_id']
        )

        # Drop the new columns
        batch_op.drop_column('archived_at')
        batch_op.drop_column('is_active')
        batch_op.drop_column('external_session_id')
        batch_op.drop_column('engine')
