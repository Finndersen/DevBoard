import datetime
import sys
from collections.abc import Generator, Iterator
from unittest.mock import AsyncMock, MagicMock, Mock

# Stub out optional SDK packages so tests can import production modules even
# when the packages are not installed in the dev/CI environment.
if "claude_interactive_sdk" not in sys.modules:
    sys.modules["claude_interactive_sdk"] = MagicMock()
if "openai_codex" not in sys.modules:
    _codex_stub = MagicMock()
    sys.modules["openai_codex"] = _codex_stub
    sys.modules["openai_codex.client"] = MagicMock()
    sys.modules["openai_codex.generated"] = MagicMock()
    sys.modules["openai_codex.generated.v2_all"] = MagicMock()
    sys.modules["openai_codex.models"] = MagicMock()

import logfire
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.run import AgentRunResult
from pytest import fixture
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from devboard.agents.config_types import AgentEngineModelConfig
from devboard.agents.engines import AgentEngine
from devboard.agents.events import MessageRole, TextMessage
from devboard.agents.language_models import LLMProvider, ModelType
from devboard.api.main import app
from devboard.db.database import get_db
from devboard.db.models import Base, Codebase, Document, Project, Task
from devboard.db.models.document import DocumentType
from devboard.db.models.language_model import LanguageModelDB
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    AgentRoleConfigRepository,
    ConfigurationRepository,
    ConversationRepository,
    DocumentRepository,
    LanguageModelRepository,
    ProjectRepository,
    TaskRepository,
)
from devboard.services.config_service import ConfigService
from devboard.services.integration_service import IntegrationService

# Disable sending to Logfire during tests, regardless of LOGFIRE_TOKEN in environment
logfire.configure(send_to_logfire=False, console=False)


@fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """
    Fixture which returns a SQLAlchemy engine for in-memory SQLite database for testing.
    """
    yield create_engine(
        "sqlite:///:memory:",
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
    from devboard.db.repositories.configuration import ConfigurationRepository

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
        # Clear the class-level config cache so rolled-back entries don't leak into subsequent tests
        ConfigurationRepository._cache.clear()


@fixture(scope="session")
def _test_client() -> Iterator[TestClient]:
    """Session-scoped TestClient to avoid MCP lifespan issues.

    The FastMCP HTTP session manager cannot be cleanly re-entered after exit,
    so we keep a single TestClient for the entire test session.
    """
    with TestClient(app) as test_client:
        yield test_client


@fixture
def client(db_session, language_model_repository, _test_client) -> Iterator[TestClient]:
    """FastAPI test client with database setup.

    Uses the session-scoped TestClient but sets up per-test database overrides
    to maintain test isolation. Seeds language models and a fake OpenAI provider
    config so AgentConfigService can resolve models from the test DB.
    """
    import json

    from devboard.db.models.configuration import Configuration

    # Seed a fake OpenAI API key so _get_all_available_internal_models() finds models
    fake_openai_config = Configuration(key="llm.openai.main", value_json=json.dumps({"api_key": "test-key"}))
    db_session.add(fake_openai_config)
    db_session.flush()

    def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db

    yield _test_client

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
def document_repository(db_session):
    """Document repository instance for testing."""
    return DocumentRepository(db_session)


@fixture
def conversation_repository(db_session):
    """Conversation repository instance for testing."""
    return ConversationRepository(db_session)


@fixture
def agent_role_config_repository(db_session):
    """AgentRoleConfigRepository instance for testing."""
    return AgentRoleConfigRepository(db_session)


@fixture
def language_model_repository(db_session):
    """LanguageModelRepository instance for testing, pre-seeded with default models."""
    from devboard.agents.language_models import DEFAULT_MODELS

    repo = LanguageModelRepository(db_session)
    if repo.count() == 0:
        for model in DEFAULT_MODELS:
            repo.create(
                provider=model.provider,
                name=model.name,
                model_type=model.model_type,
                full_name=model.full_name,
                bedrock_id=model.bedrock_id,
            )
    return repo


# Test data fixtures
@fixture
def test_codebase(db_session, tmp_path):
    """Create a test codebase DB record with a real directory for tests."""
    from devboard.db.models.codebase import Codebase
    from devboard.db.repositories import CodebaseRepository

    codebase_path = tmp_path / "test-codebase"
    codebase_path.mkdir()

    codebase_repo = CodebaseRepository(db_session)
    codebase = codebase_repo.create(
        Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path=str(codebase_path),
        )
    )
    db_session.commit()
    return codebase


@fixture
def test_task(db_session, test_codebase):
    """Create a complete test task with all required relationships."""
    from devboard.agents.engines import AgentEngine
    from devboard.agents.roles import AgentRoleType
    from devboard.db.models import ParentEntityType
    from devboard.db.models.document import DocumentType
    from devboard.db.models.task import TaskStatus
    from devboard.db.repositories import (
        ConversationRepository,
        DocumentRepository,
        ProjectRepository,
        TaskRepository,
    )

    project_repo = ProjectRepository(db_session)
    document_repo = DocumentRepository(db_session)
    task_repo = TaskRepository(db_session)
    conversation_repo = ConversationRepository(db_session)

    # Create project
    spec_doc = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(
        name="Test Project",
        description="A test project for development",
        specification=spec_doc,
    )

    # Create task
    task_spec_doc = document_repo.create(DocumentType.TASK_SPECIFICATION, "Test task specification")
    task = task_repo.create(
        project_id=project.id,
        title="Test Task",
        status=TaskStatus.PLANNING,
        specification=task_spec_doc,
        base_branch="main",
        branch_name="task-1-test-task",
        codebase_id=test_codebase.id,
    )

    # Create conversation for project
    conversation_repo.create(
        parent_entity_type=ParentEntityType.PROJECT,
        parent_entity_id=project.id,
        agent_role=AgentRoleType.PROJECT,
        engine=AgentEngine.INTERNAL,
        model_id="openai:gpt-4",
    )

    # Create conversation for task
    conversation_repo.create(
        parent_entity_type=ParentEntityType.TASK,
        parent_entity_id=task.id,
        agent_role=AgentRoleType.TASK_PLANNING,
        engine=AgentEngine.INTERNAL,
        model_id="openai:gpt-4",
    )
    db_session.commit()

    return task


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
    mock_service = Mock()
    # Return an AgentEngineModelConfig with a resolved LanguageModelDB
    mock_model = Mock(spec=LanguageModelDB)
    mock_model.provider = LLMProvider.OPENAI
    mock_model.name = "gpt-4"
    mock_model.model_type = ModelType.STANDARD
    mock_model.model_id = "openai:gpt-4"
    default_config = AgentEngineModelConfig(engine=AgentEngine.INTERNAL, model_db=mock_model)
    mock_service.get_effective_config.return_value = default_config
    # Mock methods for custom instructions and MCP tools
    mock_service.get_custom_instructions.return_value = None
    mock_service.get_enabled_mcp_tools.return_value = []
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

    # Create proper mock responses that return ConversationEvent lists
    def create_mock_events(message_text):
        return [
            TextMessage(
                role=MessageRole.AGENT,
                text_content=message_text,
                timestamp=datetime.datetime.now(datetime.UTC),
            )
        ]

    mock_message_events = create_mock_events(
        "I can help you analyze your project and answer questions about your codebase, GitHub repositories, and Jira issues."
    )

    mock_tool_approval_events = create_mock_events(
        "Great! I've processed your tool approvals and retrieved the requested information."
    )

    # Set return value based on whether it's a string prompt or tool approvals
    async def run_side_effect(prompt_or_approvals):
        if isinstance(prompt_or_approvals, str):
            return mock_message_events
        else:  # ToolApprovals
            return mock_tool_approval_events

    mock_agent.run.side_effect = run_side_effect

    # Mock stream_events to yield the same events
    async def stream_events_side_effect(prompt_or_approvals):
        events = mock_message_events if isinstance(prompt_or_approvals, str) else mock_tool_approval_events
        for event in events:
            yield event

    mock_agent.stream_events = stream_events_side_effect

    # Also need to support get_new_messages for compatibility with old tests
    mock_message_result = Mock(spec=AgentRunResult)
    mock_message_result.output = "I can help you analyze your project and answer questions about your codebase, GitHub repositories, and Jira issues."
    mock_response = ModelResponse(parts=[TextPart(content=mock_message_result.output)])
    mock_message_result.new_messages = Mock(return_value=[mock_response])

    mock_agent.last_run_result = mock_message_result
    mock_agent.get_new_messages = Mock(return_value=[mock_response])

    return mock_agent


def create_mock_task(
    task_id: int = 1,
    title: str = "Test Task",
    status: TaskStatus = TaskStatus.PLANNING,
    specification_content: str = "",
    implementation_plan_content: str | None = None,
    codebase_path: str = "/tmp/test-codebase",
    codebase_id: int | None = None,
) -> Mock:
    """Create a mock Task with codebase (now required).

    Args:
        task_id: Task ID
        title: Task title
        status: Task status
        specification_content: Content for specification document
        implementation_plan_content: Content for implementation plan document, or None to not include one
        codebase_path: Path to codebase (defaults to /tmp/test-codebase)
        codebase_id: Codebase ID (defaults to task_id * 100)

    Returns:
        Mock Task object with codebase relationship
    """
    task = Mock(spec=Task)
    task.id = task_id
    task.title = title
    task.status = status
    task.base_branch = "main"
    task.branch_name = f"task-{task_id}-{title.lower().replace(' ', '-')}"

    # Mock specification document
    spec_doc = Mock(spec=Document)
    spec_doc.id = task_id * 10
    spec_doc.document_type = DocumentType.TASK_SPECIFICATION
    spec_doc.content = specification_content
    task.specification = spec_doc

    # Mock implementation plan document (optional)
    if implementation_plan_content is not None:
        plan_doc = Mock(spec=Document)
        plan_doc.id = task_id * 10 + 1
        plan_doc.document_type = DocumentType.TASK_IMPLEMENTATION_PLAN
        plan_doc.content = implementation_plan_content
        task.implementation_plan = plan_doc
    else:
        task.implementation_plan = None

    # Codebase is now required
    codebase = Mock(spec=Codebase)
    codebase.id = codebase_id if codebase_id is not None else task_id * 100
    codebase.name = "Test Codebase"
    codebase.local_path = codebase_path
    task.codebase = codebase
    task.codebase_id = codebase.id

    # Mock project with codebases (needed for investigate_codebase tool). Defaults to a
    # top-level project (not an initiative) with its own specification document.
    project = Mock(spec=Project)
    project.id = task_id * 1000
    project.name = "Test Project"
    project.description = "A test project"
    project.codebases = [codebase]
    project.parent = None
    project.parent_project_id = None
    project.parent_project_name = None
    project.is_initiative = False
    project_spec_doc = Mock(spec=Document)
    project_spec_doc.id = task_id * 10 + 2
    project_spec_doc.document_type = DocumentType.PROJECT_SPECIFICATION
    project_spec_doc.content = "# Project Spec\n\nProject content."
    project.specification = project_spec_doc
    task.project = project
    task.project_id = project.id

    # Mock additional attributes accessed by context builders
    task.github_pr_number = None
    task.custom_fields = None
    task.implementation_plan_structured = None

    # Mock workspace directory method
    task.get_current_workspace_dir = Mock(return_value=codebase_path)

    return task


@pytest.fixture(autouse=True)
def no_real_shell_commands(monkeypatch):
    """Prevent real shell/git subprocess calls in tests.

    Tests that need git behaviour should mock GitRepoIntegration at the module
    level. Any test that reaches the actual shell execution layer has failed to
    mock properly and should fail loudly.
    """
    from devboard.integrations import shell

    async def _raise(*args, **kwargs):
        raise RuntimeError(f"Real shell command attempted in test (mock GitRepoIntegration): {args}")

    monkeypatch.setattr(shell, "execute_shell_command", _raise)
