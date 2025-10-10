"""add_agent_role_and_model_id_to_conversations

Revision ID: 0e6f210b42b8
Revises: 7b1be2f41a34
Create Date: 2025-01-10 10:14:27.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e6f210b42b8'
down_revision: Union[str, Sequence[str], None] = '7b1be2f41a34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add agent_role and model_id columns."""
    # Add columns as nullable first
    op.add_column('conversations', sa.Column('agent_role', sa.String(), nullable=True))
    op.add_column('conversations', sa.Column('model_id', sa.String(), nullable=True))

    # Backfill data
    # For now, we'll set default values. The proper backfill will happen when the service is running
    # and can properly derive agent_role from parent entities and get model_id from config
    connection = op.get_bind()

    # Update engine column to use new naming (pydantic_ai -> internal)
    connection.execute(sa.text(
        "UPDATE conversations SET engine = 'internal' WHERE engine = 'pydantic_ai'"
    ))

    # Set default agent_role based on parent_entity_type
    # Projects get PROJECT role, tasks get TASK_SPECIFICATION as default (will be corrected by service)
    connection.execute(sa.text(
        "UPDATE conversations SET agent_role = CASE "
        "WHEN parent_entity_type = 'project' THEN 'project' "
        "WHEN parent_entity_type = 'codebase' THEN 'investigation' "
        "ELSE 'task_specification' "
        "END WHERE agent_role IS NULL"
    ))

    # Set default model_id based on engine
    # This is a reasonable default that will work for most cases
    connection.execute(sa.text(
        "UPDATE conversations SET model_id = CASE "
        "WHEN engine = 'internal' THEN 'anthropic:claude-sonnet-4' "
        "WHEN engine = 'claude_code' THEN 'anthropic:claude-sonnet-4' "
        "WHEN engine = 'gemini_cli' THEN 'gemini:gemini-2.0-flash-exp' "
        "ELSE 'anthropic:claude-sonnet-4' "
        "END WHERE model_id IS NULL"
    ))

    # Make columns NOT NULL after backfill
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.alter_column('agent_role', nullable=False)
        batch_op.alter_column('model_id', nullable=False)


def downgrade() -> None:
    """Downgrade schema by removing agent_role and model_id columns."""
    # Restore old engine naming
    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE conversations SET engine = 'pydantic_ai' WHERE engine = 'internal'"
    ))

    # Drop columns
    op.drop_column('conversations', 'model_id')
    op.drop_column('conversations', 'agent_role')
