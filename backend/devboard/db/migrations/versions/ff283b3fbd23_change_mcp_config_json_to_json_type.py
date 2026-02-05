"""change_mcp_config_json_to_json_type

Revision ID: ff283b3fbd23
Revises: e1faff78d9e6
Create Date: 2026-02-05 10:50:34.394643

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ff283b3fbd23"
down_revision: str | Sequence[str] | None = "e1faff78d9e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("mcp_server_configs") as batch_op:
        batch_op.alter_column("config_json", existing_type=sa.TEXT(), type_=sa.JSON(), existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("mcp_server_configs") as batch_op:
        batch_op.alter_column("config_json", existing_type=sa.JSON(), type_=sa.TEXT(), existing_nullable=False)
