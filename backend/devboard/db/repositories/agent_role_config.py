"""Agent role configuration repository for data access operations."""

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from devboard.agents.roles import AgentRoleType
from devboard.db.models import AgentRoleConfig, MCPTool
from devboard.db.repositories.base import BaseRepository


class AgentRoleConfigRepository(BaseRepository[AgentRoleConfig]):
    """Repository for agent role configuration data access operations."""

    def get_by_role(self, role: AgentRoleType) -> AgentRoleConfig | None:
        """Get configuration for a specific agent role.

        Args:
            role: The agent role to get configuration for

        Returns:
            AgentRoleConfig if found, None otherwise
        """
        stmt = select(AgentRoleConfig).where(AgentRoleConfig.role == role)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_or_create(self, role: AgentRoleType) -> AgentRoleConfig:
        """Get existing configuration or create a new one with defaults.

        Args:
            role: The agent role to get or create configuration for

        Returns:
            Existing or newly created AgentRoleConfig
        """
        config = self.get_by_role(role)
        if config is None:
            config = AgentRoleConfig(
                role=role,
                engine=None,
                model_id=None,
                custom_instructions=None,
            )
            self.db.add(config)
            self.db.flush()
        return config

    def update(self, config: AgentRoleConfig) -> AgentRoleConfig:
        """Update an existing configuration.

        Args:
            config: The configuration to update

        Returns:
            Updated AgentRoleConfig
        """
        self.db.merge(config)
        self.db.flush()
        return config

    def add_mcp_tool(self, config_id: int, tool_id: int) -> None:
        """Add an MCP tool to a role configuration.

        Args:
            config_id: The ID of the agent role config
            tool_id: The ID of the MCP tool to add
        """
        config = self.db.get(AgentRoleConfig, config_id)
        tool = self.db.get(MCPTool, tool_id)
        if config is None or tool is None:
            raise ValueError("Config or tool not found")
        if tool not in config.enabled_mcp_tools:
            config.enabled_mcp_tools.append(tool)
            self.db.flush()

    def remove_mcp_tool(self, config_id: int, tool_id: int) -> None:
        """Remove an MCP tool from a role configuration.

        Args:
            config_id: The ID of the agent role config
            tool_id: The ID of the MCP tool to remove
        """
        config = self.db.get(AgentRoleConfig, config_id)
        tool = self.db.get(MCPTool, tool_id)
        if config is None or tool is None:
            raise ValueError("Config or tool not found")
        if tool in config.enabled_mcp_tools:
            config.enabled_mcp_tools.remove(tool)
            self.db.flush()

    def get_enabled_tools(self, role: AgentRoleType) -> list[MCPTool]:
        """Get all enabled MCP tools for a role with eager loading of server relationship.

        Args:
            role: The agent role to get enabled tools for

        Returns:
            List of MCPTool instances with server relationship loaded
        """
        stmt = (
            select(AgentRoleConfig)
            .options(joinedload(AgentRoleConfig.enabled_mcp_tools).joinedload(MCPTool.server))
            .where(AgentRoleConfig.role == role)
        )
        config = self.db.execute(stmt).unique().scalar_one_or_none()
        if config is None:
            return []
        return list(config.enabled_mcp_tools)
