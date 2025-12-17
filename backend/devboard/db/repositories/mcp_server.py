"""MCP server configuration repository for data access operations."""

from sqlalchemy import select

from devboard.db.models import MCPServerConfig
from devboard.db.repositories.base import BaseRepository


class MCPServerRepository(BaseRepository[MCPServerConfig]):
    """Repository for MCP server configuration data access operations."""

    def get_by_id(self, server_id: int) -> MCPServerConfig | None:
        stmt = select(MCPServerConfig).where(MCPServerConfig.id == server_id)
        return self.db.execute(stmt).scalar_one_or_none()

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

    def delete(self, server_id: int) -> bool:
        config = self.get_by_id(server_id)
        if config:
            self.db.delete(config)
            self.db.flush()
            return True
        return False
