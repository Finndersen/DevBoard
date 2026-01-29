"""Merge DEFINING and PLANNING task statuses

This migration updates existing data to merge the DEFINING status into PLANNING
and the TASK_SPECIFICATION role into TASK_PLANNING.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate DEFINING tasks to PLANNING and TASK_SPECIFICATION roles to TASK_PLANNING."""
    connection = op.get_bind()

    # Update tasks: DEFINING -> PLANNING
    connection.execute(sa.text("UPDATE tasks SET status = 'planning' WHERE status = 'defining'"))

    # Update conversations: TASK_SPECIFICATION -> TASK_PLANNING
    connection.execute(
        sa.text("UPDATE conversations SET agent_role = 'task_planning' WHERE agent_role = 'task_specification'")
    )


def downgrade() -> None:
    """Revert PLANNING tasks back to DEFINING and TASK_PLANNING roles back to TASK_SPECIFICATION.

    Note: This is a best-effort downgrade. Tasks that were originally PLANNING
    will remain as PLANNING (we can't distinguish them from migrated DEFINING tasks).
    """
    # No automatic downgrade - the data transformation is not reversible
    # without additional tracking of which tasks were originally DEFINING
    pass
