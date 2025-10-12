"""remove_updated_at_from_conversations

Revision ID: 95b62cbc612d
Revises: 0e6f210b42b8
Create Date: 2025-10-12 13:26:19.794196

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95b62cbc612d'
down_revision: Union[str, Sequence[str], None] = '0e6f210b42b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema by removing unused updated_at column."""
    # SQLite requires batch mode for dropping columns
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_column('updated_at')


def downgrade() -> None:
    """Downgrade schema by re-adding updated_at column."""
    op.add_column('conversations', sa.Column('updated_at', sa.DateTime(), nullable=False))
