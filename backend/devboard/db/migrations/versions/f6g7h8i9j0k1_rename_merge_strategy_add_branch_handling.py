"""Rename merge_strategy to merge_method and add branch_handling

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2025-01-25 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6g7h8i9j0k1"
down_revision: str | Sequence[str] | None = "e5f6g7h8i9j0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename merge_strategy to merge_method and add branch_handling column.

    Data migration:
    - github_pr -> branch_handling='github_pr', merge_method='squash'
    - none -> branch_handling='manual', merge_method='squash'
    - squash/rebase/merge_commit -> branch_handling='local_merge', merge_method=<existing>
    """
    # Add branch_handling column with temporary nullable
    op.add_column("codebases", sa.Column("branch_handling", sa.String(length=50), nullable=True))

    # Rename merge_strategy to merge_method
    with op.batch_alter_table("codebases") as batch_op:
        batch_op.alter_column("merge_strategy", new_column_name="merge_method")

    # Migrate data based on old merge_strategy values
    connection = op.get_bind()

    # Set branch_handling based on old merge_method values
    # github_pr -> branch_handling='github_pr', merge_method='squash'
    connection.execute(
        sa.text(
            """
            UPDATE codebases
            SET branch_handling = 'github_pr', merge_method = 'squash'
            WHERE merge_method = 'github_pr'
            """
        )
    )

    # none -> branch_handling='manual', merge_method='squash'
    connection.execute(
        sa.text(
            """
            UPDATE codebases
            SET branch_handling = 'manual', merge_method = 'squash'
            WHERE merge_method = 'none'
            """
        )
    )

    # squash/rebase/merge_commit -> branch_handling='local_merge', keep merge_method
    connection.execute(
        sa.text(
            """
            UPDATE codebases
            SET branch_handling = 'local_merge'
            WHERE branch_handling IS NULL
            """
        )
    )

    # Make branch_handling non-nullable with default
    with op.batch_alter_table("codebases") as batch_op:
        batch_op.alter_column(
            "branch_handling", existing_type=sa.String(length=50), nullable=False, server_default="local_merge"
        )


def downgrade() -> None:
    """Revert: rename merge_method back to merge_strategy and remove branch_handling.

    Data migration (lossy - cannot fully recover github_pr/none from branch_handling):
    - branch_handling='github_pr' -> merge_strategy='github_pr'
    - branch_handling='manual' -> merge_strategy='none'
    - branch_handling='local_merge' -> keep merge_strategy as is
    """
    connection = op.get_bind()

    # Restore github_pr merge_strategy
    connection.execute(
        sa.text(
            """
            UPDATE codebases
            SET merge_method = 'github_pr'
            WHERE branch_handling = 'github_pr'
            """
        )
    )

    # Restore none merge_strategy
    connection.execute(
        sa.text(
            """
            UPDATE codebases
            SET merge_method = 'none'
            WHERE branch_handling = 'manual'
            """
        )
    )

    # Drop branch_handling column
    op.drop_column("codebases", "branch_handling")

    # Rename merge_method back to merge_strategy
    with op.batch_alter_table("codebases") as batch_op:
        batch_op.alter_column("merge_method", new_column_name="merge_strategy")
