"""Add conversation_evaluations table

Revision ID: 3771444f7dc9
Revises: ebb66080d9c0
Create Date: 2025-11-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3771444f7dc9'
down_revision: Union[str, Sequence[str], None] = 'ebb66080d9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create conversation_evaluations table
    op.create_table(
        'conversation_evaluations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('evaluator_model_id', sa.String(length=255), nullable=False),
        sa.Column('overall_rating', sa.Float(), nullable=False),
        sa.Column('evaluations_json', sa.JSON(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('evaluated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index(
        'idx_evaluations_by_conversation',
        'conversation_evaluations',
        ['conversation_id', 'evaluated_at']
    )
    op.create_index(
        'idx_evaluations_by_rating',
        'conversation_evaluations',
        ['overall_rating']
    )
    op.create_index(
        'idx_evaluations_by_date',
        'conversation_evaluations',
        ['evaluated_at']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_evaluations_by_date', table_name='conversation_evaluations')
    op.drop_index('idx_evaluations_by_rating', table_name='conversation_evaluations')
    op.drop_index('idx_evaluations_by_conversation', table_name='conversation_evaluations')

    # Drop table
    op.drop_table('conversation_evaluations')
