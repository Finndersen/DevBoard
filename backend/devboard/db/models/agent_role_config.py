"""Agent role configuration database model."""

from typing import TYPE_CHECKING

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType

from .base import Base

if TYPE_CHECKING:
    from .mcp_server import MCPTool


# Junction table for many-to-many relationship between AgentRoleConfig and MCPTool
agent_role_config_mcp_tools = Table(
    "agent_role_config_mcp_tools",
    Base.metadata,
    Column("agent_role_config_id", Integer, ForeignKey("agent_role_configs.id", ondelete="CASCADE"), primary_key=True),
    Column("mcp_tool_id", Integer, ForeignKey("mcp_tools.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("agent_role_config_id", "mcp_tool_id", name="uq_agent_role_config_mcp_tool"),
)


class AgentRoleConfig(Base):
    """Configuration for a specific agent role."""

    __tablename__ = "agent_role_configs"
    __table_args__ = (UniqueConstraint("role", name="uq_agent_role_config_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[AgentRoleType] = mapped_column(Enum(AgentRoleType))
    engine: Mapped[AgentEngine | None] = mapped_column(Enum(AgentEngine), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Many-to-many relationship to MCPTool
    enabled_mcp_tools: Mapped[list["MCPTool"]] = relationship(
        "MCPTool",
        secondary=agent_role_config_mcp_tools,
        lazy="selectin",
    )
