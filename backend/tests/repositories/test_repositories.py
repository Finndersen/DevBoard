"""Tests for repository classes."""

import pytest
from sqlalchemy.orm import Session

from devboard.db.models import (
    Codebase,
    Configuration,
    ContextProviderResource,
    Project,
    ProjectConversationMessage,
)
from devboard.db.repositories import (
    CodebaseRepository,
    ConfigurationRepository,
    ContextProviderResourceRepository,
    ProjectConversationMessageRepository,
    ProjectRepository,
    TaskRepository,
)


class TestProjectRepository:
    """Tests for ProjectRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ProjectRepository:
        return ProjectRepository(db_session)

    @pytest.fixture
    def sample_project_data(self) -> dict:
        return {"name": "Test Project", "description": "A test project"}

    def test_create_project(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test creating a new project."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        assert created.id is not None
        assert created.name == "Test Project"
        assert created.description == "A test project"

    def test_get_by_id(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test getting a project by ID."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repo: ProjectRepository):
        """Test getting a project by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all(self, repo: ProjectRepository, db_session):
        """Test getting all projects."""
        repo.create(name="Project 1", description="")
        repo.create(name="Project 2", description="")
        db_session.commit()

        all_projects = repo.get_all()
        assert len(all_projects) == 2
        project_names = [p.name for p in all_projects]
        assert "Project 1" in project_names
        assert "Project 2" in project_names

    def test_update_project(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test updating a project."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        created.name = "Updated Project"
        created.description = "Updated description"

        updated = repo.update(created)
        db_session.commit()
        assert updated.name == "Updated Project"
        assert updated.description == "Updated description"

    def test_delete_by_id(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test deleting a project by ID."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        result = repo.delete_by_id(created.id)
        db_session.commit()

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ProjectRepository):
        """Test deleting a project by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False


class TestCodebaseRepository:
    """Tests for CodebaseRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> CodebaseRepository:
        return CodebaseRepository(db_session)

    @pytest.fixture
    def sample_codebase(self) -> Codebase:
        return Codebase(
            name="Test Codebase",
            description="A test codebase",
            repository_url="https://github.com/test/repo",
            local_path="/path/to/repo",
        )

    def test_create_codebase(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test creating a new codebase."""
        created = repo.create(sample_codebase)
        assert created.id is not None
        assert created.name == "Test Codebase"
        assert created.repository_url == "https://github.com/test/repo"
        assert created.description == "A test codebase"

    def test_get_by_id(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test getting a codebase by ID."""
        created = repo.create(sample_codebase)
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repo: CodebaseRepository):
        """Test getting a codebase by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all(self, repo: CodebaseRepository):
        """Test getting all codebases."""
        codebase1 = Codebase(
            name="Repo 1",
            description="",
            repository_url="https://github.com/test/repo1",
            local_path="/path/to/repo1",
        )
        codebase2 = Codebase(
            name="Repo 2",
            description="",
            repository_url="https://github.com/test/repo2",
            local_path="/path/to/repo2",
        )

        repo.create(codebase1)
        repo.create(codebase2)

        all_codebases = repo.get_all()
        assert len(all_codebases) == 2
        codebase_names = [c.name for c in all_codebases]
        assert "Repo 1" in codebase_names
        assert "Repo 2" in codebase_names

    def test_update_codebase(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test updating a codebase."""
        created = repo.create(sample_codebase)
        created.name = "Updated Codebase"
        created.description = "Updated description"

        updated = repo.update(created)
        assert updated.name == "Updated Codebase"
        assert updated.description == "Updated description"

    def test_delete_by_id(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test deleting a codebase by ID."""
        created = repo.create(sample_codebase)
        result = repo.delete_by_id(created.id)

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: CodebaseRepository):
        """Test deleting a codebase by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False


class TestTaskRepository:
    """Tests for TaskRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> TaskRepository:
        return TaskRepository(db_session)

    @pytest.fixture
    def project(self, db_session: Session) -> Project:
        """Create a test project for task relationships."""
        from devboard.db.repositories.project import ProjectRepository

        project_repo = ProjectRepository(db_session)
        project = project_repo.create(name="Test Project", description="")
        db_session.flush()
        return project

    @pytest.fixture
    def sample_task_data(self, project: Project) -> dict:
        return {
            "title": "Test Task",
            "project_id": project.id,
        }

    def test_create_task(self, repo: TaskRepository, sample_task_data: dict, db_session):
        """Test creating a new task."""
        created = repo.create(**sample_task_data)
        db_session.commit()
        assert created.id is not None
        assert created.title == "Test Task"
        assert created.status.value == "defining"  # Default status

    def test_get_by_id(self, repo: TaskRepository, sample_task_data: dict, db_session):
        """Test getting a task by ID."""
        created = repo.create(**sample_task_data)
        db_session.commit()
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title

    def test_get_by_id_not_found(self, repo: TaskRepository):
        """Test getting a task by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all_without_filter(self, repo: TaskRepository, project: Project, db_session):
        """Test getting all tasks without project filter."""
        from devboard.db.models.task import TaskStatus

        repo.create(project_id=project.id, title="Task 1")
        repo.create(project_id=project.id, title="Task 2", status=TaskStatus.COMPLETE)
        db_session.commit()

        all_tasks = repo.get_all()
        assert len(all_tasks) == 2
        task_titles = [t.title for t in all_tasks]
        assert "Task 1" in task_titles
        assert "Task 2" in task_titles

    def test_get_all_with_project_filter(self, repo: TaskRepository, project: Project, db_session: Session):
        """Test getting all tasks filtered by project."""
        from devboard.db.repositories.project import ProjectRepository

        # Create another project
        project_repo = ProjectRepository(db_session)
        project2 = project_repo.create(name="Project 2", description="")
        db_session.flush()

        repo.create(project_id=project.id, title="Task 1")
        repo.create(project_id=project2.id, title="Task 2")
        db_session.commit()

        project_tasks = repo.get_for_project(project.id)
        assert len(project_tasks) == 1
        assert project_tasks[0].title == "Task 1"
        assert project_tasks[0].project_id == project.id

    def test_get_by_project(self, repo: TaskRepository, project: Project, db_session):
        """Test getting tasks by project."""
        from devboard.db.models.task import TaskStatus

        repo.create(project_id=project.id, title="Task 1")
        repo.create(project_id=project.id, title="Task 2", status=TaskStatus.COMPLETE)
        db_session.commit()

        project_tasks = repo.get_for_project(project.id)
        assert len(project_tasks) == 2
        for task in project_tasks:
            assert task.project_id == project.id

    def test_update_task(self, repo: TaskRepository, sample_task_data: dict, db_session):
        """Test updating a task."""
        from devboard.db.models.task import TaskStatus

        created = repo.create(**sample_task_data)
        db_session.commit()
        created.title = "Updated Task"
        created.status = TaskStatus.COMPLETE

        updated = repo.update(created)
        db_session.commit()
        assert updated.title == "Updated Task"
        assert updated.status == TaskStatus.COMPLETE

    def test_delete_by_id(self, repo: TaskRepository, sample_task_data: dict, db_session):
        """Test deleting a task by ID."""
        created = repo.create(**sample_task_data)
        db_session.commit()
        result = repo.delete_by_id(created.id)
        db_session.commit()

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: TaskRepository):
        """Test deleting a task by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False


class TestConfigurationRepository:
    """Tests for ConfigurationRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ConfigurationRepository:
        return ConfigurationRepository(db_session)

    @pytest.fixture
    def sample_config(self) -> Configuration:
        return Configuration(key="test.setting", value_json="test_value")

    def test_create_configuration(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test creating a new configuration."""
        created = repo.create(sample_config)
        assert created.key == "test.setting"
        assert created.value_json == "test_value"

    def test_get_by_key(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test getting a configuration by key."""
        repo.create(sample_config)
        retrieved = repo.get_by_key("test.setting")

        assert retrieved is not None
        assert retrieved.key == "test.setting"
        assert retrieved.value_json == "test_value"

    def test_get_by_key_not_found(self, repo: ConfigurationRepository):
        """Test getting a configuration by key when it doesn't exist."""
        result = repo.get_by_key("nonexistent.key")
        assert result is None

    def test_get_all_without_prefix(self, repo: ConfigurationRepository):
        """Test getting all configurations without prefix filter."""
        config1 = Configuration(key="app.setting1", value_json="value1")
        config2 = Configuration(key="db.setting2", value_json="value2")

        repo.create(config1)
        repo.create(config2)

        all_configs = repo.get_all()
        assert len(all_configs) == 2
        config_keys = [c.key for c in all_configs]
        assert "app.setting1" in config_keys
        assert "db.setting2" in config_keys

    def test_get_all_with_prefix(self, repo: ConfigurationRepository):
        """Test getting configurations filtered by prefix."""
        config1 = Configuration(key="app.setting1", value_json="value1")
        config2 = Configuration(key="app.setting2", value_json="value2")
        config3 = Configuration(key="db.setting", value_json="value3")

        repo.create(config1)
        repo.create(config2)
        repo.create(config3)

        app_configs = repo.get_all(prefix="app.")
        assert len(app_configs) == 2
        for config in app_configs:
            assert config.key.startswith("app.")

    def test_update_configuration(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test updating a configuration."""
        created = repo.create(sample_config)
        created.value_json = "updated_value"

        updated = repo.update(created)
        assert updated.value_json == "updated_value"

    def test_delete_by_key(self, repo: ConfigurationRepository, sample_config: Configuration):
        """Test deleting a configuration by key."""
        repo.create(sample_config)
        result = repo.delete_by_key("test.setting")

        assert result is True
        assert repo.get_by_key("test.setting") is None

    def test_delete_by_key_not_found(self, repo: ConfigurationRepository):
        """Test deleting a configuration by key when it doesn't exist."""
        result = repo.delete_by_key("nonexistent.key")
        assert result is False


class TestContextProviderResourceRepository:
    """Tests for ContextProviderResourceRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ContextProviderResourceRepository:
        return ContextProviderResourceRepository(db_session)

    @pytest.fixture
    def sample_resource(self) -> ContextProviderResource:
        return ContextProviderResource(
            provider_name="github",
            resource_uri="https://github.com/test/repo",
            description="Test repository",
        )

    def test_create_resource(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test creating a new context provider resource."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        assert created.id is not None
        assert created.description == "Test repository"
        assert created.provider_name == "github"

    def test_get_by_id(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test getting a resource by ID."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.resource_uri == created.resource_uri

    def test_get_by_id_not_found(self, repo: ContextProviderResourceRepository):
        """Test getting a resource by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_resources_for_project(self, repo: ContextProviderResourceRepository):
        """Test getting resources linked to a project."""
        # Create resources using the correct API
        resource1 = repo.create_resource(
            resource_uri="https://github.com/test/repo1",
            provider_name="github",
            description="Test repo 1",
        )
        resource2 = repo.create_resource(
            resource_uri="https://jira.example.com/issue/123",
            provider_name="jira",
            description="Test issue",
        )
        resource3 = repo.create_resource(
            resource_uri="https://github.com/test/repo2",
            provider_name="github",
            description="Test repo 2",
        )

        # Link resources to projects
        repo.link_resource_to_project(resource1.id, 1)
        repo.link_resource_to_project(resource2.id, 1)
        repo.link_resource_to_project(resource3.id, 2)

        # Test getting resources for project 1
        results = repo.get_resources_for_project(1)
        assert len(results) == 2
        resource_uris = {r.resource_uri for r in results}
        assert "https://github.com/test/repo1" in resource_uris
        assert "https://jira.example.com/issue/123" in resource_uris

        # Test getting resources for project 2
        results2 = repo.get_resources_for_project(2)
        assert len(results2) == 1
        assert results2[0].resource_uri == "https://github.com/test/repo2"

    def test_update_resource(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test updating a context provider resource."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        created.provider_name = "updated_provider"
        created.resource_uri = "https://example.com/updated"

        updated = repo.update(created)
        assert updated.provider_name == "updated_provider"
        assert updated.resource_uri == "https://example.com/updated"

    def test_delete_by_id(
        self,
        repo: ContextProviderResourceRepository,
        sample_resource: ContextProviderResource,
    ):
        """Test deleting a resource by ID."""
        created = repo.create_resource(
            resource_uri=sample_resource.resource_uri,
            provider_name=sample_resource.provider_name,
            description=sample_resource.description,
        )
        result = repo.delete_resource(created.id)

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ContextProviderResourceRepository):
        """Test deleting a resource by ID when it doesn't exist."""
        result = repo.delete_resource(999)
        assert result is False

    def test_delete_project_resource_with_cascade(self, repo: ContextProviderResourceRepository):
        """Test deleting project resource with cascade deletion when orphaned."""
        # Create resources
        resource1 = repo.create_resource(
            resource_uri="https://github.com/test/repo1",
            provider_name="github",
            description="Test repo 1",
        )
        resource2 = repo.create_resource(
            resource_uri="https://jira.example.com/issue/123",
            provider_name="jira",
            description="Test issue",
        )

        # Link both resources to project 1
        repo.link_resource_to_project(resource1.id, 1)
        repo.link_resource_to_project(resource2.id, 1)

        # Also link resource1 to project 2 (so it won't be cascade deleted)
        repo.link_resource_to_project(resource1.id, 2)

        # Delete resource1 from project 1 - should not cascade delete (still linked to project 2)
        result1 = repo.delete_project_resource(1, resource1.id)
        assert result1 is True
        assert repo.get_by_id(resource1.id) is not None  # Still exists

        # Delete resource2 from project 1 - should cascade delete (becomes orphaned)
        result2 = repo.delete_project_resource(1, resource2.id)
        assert result2 is True
        assert repo.get_by_id(resource2.id) is None  # Cascade deleted

        # Verify project 1 has no more resources
        remaining_resources = repo.get_resources_for_project(1)
        assert len(remaining_resources) == 0

        # Verify project 2 still has resource1
        project2_resources = repo.get_resources_for_project(2)
        assert len(project2_resources) == 1
        assert project2_resources[0].id == resource1.id


class TestProjectConversationMessageRepository:
    """Tests for ProjectConversationMessageRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ProjectConversationMessageRepository:
        return ProjectConversationMessageRepository(db_session)

    @pytest.fixture
    def project(self, db_session: Session) -> Project:
        """Create a test project for message relationships."""
        from devboard.db.repositories.project import ProjectRepository

        project_repo = ProjectRepository(db_session)
        project = project_repo.create(name="Test Project", description="")
        db_session.flush()
        return project

    @pytest.fixture
    def sample_message(self, project: Project) -> ProjectConversationMessage:
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        pydantic_message = ModelRequest(parts=[UserPromptPart(content="Test message")])
        return ProjectConversationMessage.from_pydantic_message(project.id, pydantic_message)

    def test_create_message(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test creating a new message."""
        created = repo.create(sample_message)
        db_session.commit()
        assert created.id is not None
        assert created.text_content == "Test message"

    def test_get_by_id(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test getting a message by ID."""
        created = repo.create(sample_message)
        db_session.commit()
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.text_content == created.text_content

    def test_get_by_id_not_found(self, repo: ProjectConversationMessageRepository):
        """Test getting a message by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all_for_entity(self, repo: ProjectConversationMessageRepository, project: Project, db_session):
        """Test getting all messages for an entity, ordered by timestamp."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        message1 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelRequest(parts=[UserPromptPart(content="First message")])
        )
        message2 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="Second message")])
        )

        # Create in reverse order to test ordering
        repo.create(message2)
        repo.create(message1)
        db_session.commit()

        messages = repo.get_all_for_entity(project.id)
        assert len(messages) == 2
        # Should be ordered by timestamp ascending
        assert messages[0].timestamp <= messages[1].timestamp

    def test_update_message(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test updating a message."""
        from pydantic_ai.messages import ModelResponse, TextPart
        from pydantic_core import to_jsonable_python

        from devboard.db.models.messages import _get_message_type

        created = repo.create(sample_message)
        db_session.commit()

        # Update to a response message
        response_message = ModelResponse(parts=[TextPart(content="Updated message content")])
        created.pydantic_content = to_jsonable_python(response_message)
        created.message_type = _get_message_type(response_message)

        updated = repo.update(created)
        db_session.commit()
        assert updated.text_content == "Updated message content"

    def test_delete_by_id(
        self,
        repo: ProjectConversationMessageRepository,
        sample_message: ProjectConversationMessage,
        db_session,
    ):
        """Test deleting a message by ID."""
        created = repo.create(sample_message)
        db_session.commit()
        result = repo.delete_by_id(created.id)
        db_session.commit()

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ProjectConversationMessageRepository):
        """Test deleting a message by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False

    def test_delete_all_for_entity(self, repo: ProjectConversationMessageRepository, project: Project, db_session):
        """Test deleting all messages for an entity."""
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        message1 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelRequest(parts=[UserPromptPart(content="Message 1")])
        )
        message2 = ProjectConversationMessage.from_pydantic_message(
            project.id, ModelResponse(parts=[TextPart(content="Message 2")])
        )

        repo.create(message1)
        repo.create(message2)
        db_session.commit()

        count = repo.delete_all_for_entity(project.id)
        db_session.commit()
        assert count == 2

        remaining_messages = repo.get_all_for_entity(project.id)
        assert len(remaining_messages) == 0
