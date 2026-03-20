"""MCP dependency management.

This module provides dependency injection helpers for MCP tools.

Note: MCP tools cannot use FastAPI's Depends() because they are invoked through
the MCP protocol, not through FastAPI request handlers. FastMCP's Context-based
injection is incompatible with FastAPI's dependency injection system.

Instead, we use manual dependency management with context managers and factory
functions that mimic the structure of FastAPI dependencies.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.engines.agent_engines import agent_engine_registry
from devboard.agents.language_models import llm_registry
from devboard.db.database import SessionLocal
from devboard.db.repositories import AgentRoleConfigRepository, ConfigurationRepository
from devboard.services.config_service import ConfigService


@contextmanager
def get_mcp_db_session() -> Generator[Session]:
    """Context manager for MCP tool database sessions.

    Provides proper transaction management with commit/rollback and cleanup.
    Use this in MCP tools that need database access.

    Example:
        with get_mcp_db_session() as db:
            repo = ProjectRepository(db)
            projects = repo.get_all()

    Yields:
        Database session with automatic commit/rollback/cleanup
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_agent_config_service(db: Session) -> AgentConfigService:
    """Create AgentConfigService instance for MCP tools.

    This follows the same dependency chain as FastAPI's get_agent_config_service:
    ConfigurationRepository -> ConfigService -> AgentConfigService

    Args:
        db: Database session

    Returns:
        AgentConfigService instance with LLM and engine registries
    """
    config_repo = ConfigurationRepository(db)
    config_service = ConfigService(config_repo)
    agent_role_config_repo = AgentRoleConfigRepository(db)
    return AgentConfigService(
        agent_role_config_repo=agent_role_config_repo,
        config_service=config_service,
        llm_registry=llm_registry,
        engine_registry=agent_engine_registry,
    )
