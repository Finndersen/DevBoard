"""Make task implementation_plan_id mandatory

Revision ID: dc1ed364140a
Revises: d7f5867373fc
Create Date: 2025-09-16 01:33:01.151296

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc1ed364140a'
down_revision: Union[str, Sequence[str], None] = 'd7f5867373fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # First, update any existing tasks that don't have implementation_plan_id
    connection = op.get_bind()
    
    # Check if any tasks exist without implementation_plan_id
    result = connection.execute(sa.text(
        "SELECT COUNT(*) FROM tasks WHERE implementation_plan_id IS NULL"
    )).scalar()
    
    if result > 0:
        # For any tasks missing implementation_plan_id, create empty documents
        # Note: This requires the documents table to exist
        missing_tasks = connection.execute(sa.text(
            "SELECT id FROM tasks WHERE implementation_plan_id IS NULL"
        )).fetchall()
        
        for (task_id,) in missing_tasks:
            # Create an empty implementation plan document
            connection.execute(sa.text(
                "INSERT INTO documents (document_type, content, content_hash) VALUES (?, ?, ?)"
            ), ("task_implementation_plan", "", ""))
            
            # Get the last inserted document ID
            doc_id = connection.execute(sa.text("SELECT last_insert_rowid()")).scalar()
            
            # Update the task with the new document ID
            connection.execute(sa.text(
                "UPDATE tasks SET implementation_plan_id = ? WHERE id = ?"
            ), (doc_id, task_id))
    
    # Now we can safely make the column NOT NULL using table recreation
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('implementation_plan_id',
                   existing_type=sa.INTEGER(),
                   nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Make implementation_plan_id nullable again
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.alter_column('implementation_plan_id',
                   existing_type=sa.INTEGER(),
                   nullable=True)
