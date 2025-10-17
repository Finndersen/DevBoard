"""make_task_implementation_plan_id_optional

Revision ID: 5284fb35291f
Revises: 95b62cbc612d
Create Date: 2025-10-15 23:23:57.258189

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5284fb35291f'
down_revision: Union[str, Sequence[str], None] = '95b62cbc612d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('implementation_plan_id',
                              existing_type=sa.INTEGER(),
                              nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('implementation_plan_id',
                              existing_type=sa.INTEGER(),
                              nullable=False)
