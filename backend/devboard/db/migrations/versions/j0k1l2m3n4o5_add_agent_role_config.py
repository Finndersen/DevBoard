"""add_agent_role_config

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-02-07 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j0k1l2m3n4o5"
down_revision: str | Sequence[str] | None = "i9j0k1l2m3n4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create agent_role_configs table
    op.create_table(
        "agent_role_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "project",
                "task_planning",
                "task_implementation",
                "task_pr_review",
                "investigation",
                name="agentroletype",
            ),
            nullable=False,
        ),
        sa.Column(
            "engine",
            sa.Enum("internal", "claude_code", "gemini_cli", name="agentengine"),
            nullable=True,
        ),
        sa.Column("model_id", sa.String(length=255), nullable=True),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role", name="uq_agent_role_config_role"),
    )

    # Create junction table for agent_role_config <-> mcp_tools
    op.create_table(
        "agent_role_config_mcp_tools",
        sa.Column("agent_role_config_id", sa.Integer(), nullable=False),
        sa.Column("mcp_tool_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_role_config_id"],
            ["agent_role_configs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mcp_tool_id"],
            ["mcp_tools.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_role_config_id", "mcp_tool_id"),
        sa.UniqueConstraint("agent_role_config_id", "mcp_tool_id", name="uq_agent_role_config_mcp_tool"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("agent_role_config_mcp_tools")
    op.drop_table("agent_role_configs")

    # Drop enums if they were created
    op.execute("DROP TYPE IF EXISTS agentroletype")
    op.execute("DROP TYPE IF EXISTS agentengine")
