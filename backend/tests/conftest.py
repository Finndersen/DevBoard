from collections.abc import Generator
from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.run import AgentRunResult
from pytest import fixture
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from devboard.api.main import app
from devboard.db.database import get_db
from devboard.db.models import Base
from devboard.db.repositories import (
    ConfigurationRepository,
    ContextProviderResourceRepository,
    ConversationRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.config_service import ConfigService
from devboard.services.integration_service import IntegrationService


@fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """
    Fixture which returns a SQLAlchemy engine for in-memory SQLite database for testing.
    """
    yield create_engine(
        "sqlite:///:memory:",
        echo=True,
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )


@fixture(scope="session")
def db_connection(db_engine: Engine) -> Generator[Connection, None, None]:
    """
    Fixture to provide a SQLAlchemy connection for the containerised database.
    This connection is re-used for the entire test session.
    """
    with db_engine.connect() as connection:
        yield connection


@fixture(scope="session")
def db_tables(db_connection):
    """
    Fixture to create all the tables in the database.
    Dropping tables afterwards should not be necessary since the entire container will be cleared
    """
    with db_connection.begin():
        Base.metadata.create_all(db_connection)
    yield


@fixture()
def db_session(db_connection: Connection, db_tables) -> Generator[Session, None, None]:
    """
    Provides a SQLAlchemy DB session that automatically rolls back changes after each test.
    """
    # Use savepoint/nested transaction for proper test isolation in SQLite
    nested_trans = db_connection.begin_nested()

    # Create session bound to the connection
    session = Session(bind=db_connection)

    try:
        yield session
    finally:
        # Close session and rollback the savepoint
        session.close()
        nested_trans.rollback()


@fixture
def client(db_session):
    """FastAPI test client with database setup."""

    def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# Repository fixtures
@fixture
def configuration_repository(db_session):
    """Configuration repository instance for testing."""
    return ConfigurationRepository(db_session)


@fixture
def project_repository(db_session):
    """Project repository instance for testing."""
    return ProjectRepository(db_session)


@fixture
def task_repository(db_session):
    """Task repository instance for testing."""
    return TaskRepository(db_session)


@fixture
def context_provider_resource_repository(db_session):
    """Context provider resource repository instance for testing."""
    return ContextProviderResourceRepository(db_session)


@fixture
def document_repository(db_session):
    """Document repository instance for testing."""
    return DocumentRepository(db_session)


@fixture
def conversation_repository(db_session):
    """Conversation repository instance for testing."""
    return ConversationRepository(db_session)


# Service fixtures with real repositories (no mocking at service level)
@fixture
def config_service(configuration_repository):
    """ConfigService instance with real repository for testing."""
    return ConfigService(configuration_repository)


@fixture
def integration_service(configuration_repository):
    """IntegrationService instance with real repository for testing."""
    return IntegrationService(configuration_repository)


# Mock fixtures
@fixture
def mock_agent_config_service():
    """Mock AgentConfigService to avoid database dependencies."""
    from devboard.agents.agent_config_service import AgentEngineModelConfig
    from devboard.agents.engines.agent_engines import AgentEngine

    mock_service = Mock()
    # Return an AgentEngineModelConfig with model_id
    default_config = AgentEngineModelConfig(engine=AgentEngine.INTERNAL, model_id="openai:gpt-4")
    mock_service.get_effective_config.return_value = default_config
    return mock_service


@fixture
def mock_llm_service(mock_agent_config_service):
    """Alias for mock_agent_config_service for backward compatibility."""
    return mock_agent_config_service


@fixture
def mock_agent():
    """Mock project agent."""
    mock_agent = Mock()
    mock_agent.run = AsyncMock()

    # Create proper mock responses with new_messages() method
    def create_mock_result(message_text):
        mock_result = Mock(spec=AgentRunResult)
        mock_result.output = message_text

        # Mock the new_messages() method to return a list containing the response
        mock_response = ModelResponse(parts=[TextPart(content=message_text)])
        mock_result.new_messages = Mock(return_value=[mock_response])

        return mock_result

    mock_message_result = create_mock_result(
        "I can help you analyze your project and answer questions about your codebase, GitHub repositories, and Jira issues."
    )

    mock_tool_approval_result = create_mock_result(
        "Great! I've processed your tool approvals and retrieved the requested information."
    )

    # Set return value based on whether it's a string prompt or tool approvals
    def run_side_effect(prompt_or_approvals, conversation_history, deps):
        if isinstance(prompt_or_approvals, str):
            return mock_message_result
        else:  # DeferredToolApprovalResult
            return mock_tool_approval_result

    mock_agent.run.side_effect = run_side_effect

    return mock_agent
