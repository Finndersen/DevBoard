"""MCP server configuration repository for data access operations."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from devboard.db.models import MCPServerConfig, MCPTool
from devboard.db.repositories.base import BaseRepository


class MCPServerRepository(BaseRepository[MCPServerConfig]):
    """Repository for MCP server configuration data access operations."""

    def get_by_id(self, server_id: int) -> MCPServerConfig | None:
        stmt = select(MCPServerConfig).where(MCPServerConfig.id == server_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_id_with_tools(self, server_id: int) -> MCPServerConfig | None:
        stmt = select(MCPServerConfig).options(joinedload(MCPServerConfig.tools)).where(MCPServerConfig.id == server_id)
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_all(self) -> list[MCPServerConfig]:
        stmt = select(MCPServerConfig).order_by(MCPServerConfig.name)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, config: MCPServerConfig) -> MCPServerConfig:
        self.db.add(config)
        self.db.flush()
        return config

    def update(self, config: MCPServerConfig) -> MCPServerConfig:
        self.db.merge(config)
        self.db.flush()
        return config

    def update_verification_status(self, config: MCPServerConfig, *, success: bool, error: str | None) -> None:
        config.last_verified_at = datetime.now(UTC)
        config.last_verified_success = success
        config.last_verified_error = error
        self.db.merge(config)
        self.db.flush()

    def delete(self, server_id: int) -> bool:
        config = self.get_by_id(server_id)
        if config:
            self.db.delete(config)
            self.db.flush()
            return True
        return False

    # Tool-related methods

    def get_tools_by_server_id(self, server_id: int) -> list[MCPTool]:
        stmt = select(MCPTool).where(MCPTool.server_id == server_id).order_by(MCPTool.name)
        return list(self.db.execute(stmt).scalars().all())

    def get_tool_by_id(self, tool_id: int) -> MCPTool | None:
        stmt = select(MCPTool).where(MCPTool.id == tool_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_tool_by_server_and_name(self, server_id: int, name: str) -> MCPTool | None:
        stmt = select(MCPTool).where(MCPTool.server_id == server_id, MCPTool.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_tool(self, tool: MCPTool) -> MCPTool:
        self.db.add(tool)
        self.db.flush()
        return tool

    def update_tool(self, tool: MCPTool) -> MCPTool:
        self.db.merge(tool)
        self.db.flush()
        return tool

    def delete_tools_by_ids(self, tool_ids: list[int]) -> int:
        if not tool_ids:
            return 0
        stmt = select(MCPTool).where(MCPTool.id.in_(tool_ids))
        tools = list(self.db.execute(stmt).scalars().all())
        for tool in tools:
            self.db.delete(tool)
        self.db.flush()
        return len(tools)

    def expire(self, config: MCPServerConfig) -> None:
        """Expire cached state to force fresh load from database."""
        self.db.expire(config)

    def get_all_tools_from_verified_servers(self) -> list[MCPTool]:
        """Get all tools from MCP servers that have been successfully verified.

        Returns:
            List of MCPTool instances from servers where last_verified_success is True.
        """
        stmt = (
            select(MCPTool)
            .join(MCPServerConfig)
            .where(MCPServerConfig.last_verified_success.is_(True))
            .options(joinedload(MCPTool.server))
            .order_by(MCPServerConfig.name, MCPTool.name)
        )
        return list(self.db.execute(stmt).scalars().unique().all())
