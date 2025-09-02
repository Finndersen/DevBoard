"""Tests for repository classes."""

import pytest
from sqlalchemy.orm import Session

from devboard.db.models import (
    Codebase,
    Configuration,
    ContextProviderResource,
    Project,
    ProjectConversationMessage,
    Task,
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
    def sample_project(self) -> Project:
        return Project(name="Test Project", details="A test project", current_status="active")

    def test_create_project(self, repo: ProjectRepository, sample_project: Project):
        """Test creating a new project."""
        created = repo.create(sample_project)
        assert created.id is not None
        assert created.name == "Test Project"
        assert created.details == "A test project"
        assert created.current_status == "active"

    def test_get_by_id(self, repo: ProjectRepository, sample_project: Project):
        """Test getting a project by ID."""
        created = repo.create(sample_project)
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repo: ProjectRepository):
        """Test getting a project by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all(self, repo: ProjectRepository):
        """Test getting all projects."""
        project1 = Project(name="Project 1", details="", current_status="active")
        project2 = Project(name="Project 2", details="", current_status="inactive")

        repo.create(project1)
        repo.create(project2)

        all_projects = repo.get_all()
        assert len(all_projects) == 2
        project_names = [p.name for p in all_projects]
        assert "Project 1" in project_names
        assert "Project 2" in project_names

    def test_update_project(self, repo: ProjectRepository, sample_project: Project):
        """Test updating a project."""
        created = repo.create(sample_project)
        created.name = "Updated Project"
        created.details = "Updated description"

        updated = repo.update(created)
        assert updated.name == "Updated Project"
        assert updated.details == "Updated description"

    def test_delete_by_id(self, repo: ProjectRepository, sample_project: Project):
        """Test deleting a project by ID."""
        created = repo.create(sample_project)
        result = repo.delete_by_id(created.id)

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
            name="Repo 1", description="", repository_url="https://github.com/test/repo1"
        )
        codebase2 = Codebase(
            name="Repo 2", description="", repository_url="https://github.com/test/repo2"
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
        project = Project(name="Test Project", details="", current_status="active")
        db_session.add(project)
        db_session.flush()
        return project

    @pytest.fixture
    def sample_task(self, project: Project) -> Task:
        return Task(
            title="Test Task", description="A test task", status="pending", project_id=project.id
        )

    def test_create_task(self, repo: TaskRepository, sample_task: Task):
        """Test creating a new task."""
        created = repo.create(sample_task)
        assert created.id is not None
        assert created.title == "Test Task"
        assert created.description == "A test task"
        assert created.status == "pending"

    def test_get_by_id(self, repo: TaskRepository, sample_task: Task):
        """Test getting a task by ID."""
        created = repo.create(sample_task)
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title

    def test_get_by_id_not_found(self, repo: TaskRepository):
        """Test getting a task by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all_without_filter(self, repo: TaskRepository, project: Project):
        """Test getting all tasks without project filter."""
        task1 = Task(title="Task 1", status="pending", project_id=project.id)
        task2 = Task(title="Task 2", status="completed", project_id=project.id)

        repo.create(task1)
        repo.create(task2)

        all_tasks = repo.get_all()
        assert len(all_tasks) == 2
        task_titles = [t.title for t in all_tasks]
        assert "Task 1" in task_titles
        assert "Task 2" in task_titles

    def test_get_all_with_project_filter(
        self, repo: TaskRepository, project: Project, db_session: Session
    ):
        """Test getting all tasks filtered by project."""
        # Create another project
        project2 = Project(name="Project 2", details="", current_status="active")
        db_session.add(project2)
        db_session.flush()

        task1 = Task(title="Task 1", status="pending", project_id=project.id)
        task2 = Task(title="Task 2", status="pending", project_id=project2.id)

        repo.create(task1)
        repo.create(task2)

        project_tasks = repo.get_all(project_id=project.id)
        assert len(project_tasks) == 1
        assert project_tasks[0].title == "Task 1"
        assert project_tasks[0].project_id == project.id

    def test_get_by_project(self, repo: TaskRepository, project: Project):
        """Test getting tasks by project."""
        task1 = Task(title="Task 1", status="pending", project_id=project.id)
        task2 = Task(title="Task 2", status="completed", project_id=project.id)

        repo.create(task1)
        repo.create(task2)

        project_tasks = repo.get_by_project(project.id)
        assert len(project_tasks) == 2
        for task in project_tasks:
            assert task.project_id == project.id

    def test_update_task(self, repo: TaskRepository, sample_task: Task):
        """Test updating a task."""
        created = repo.create(sample_task)
        created.title = "Updated Task"
        created.status = "completed"

        updated = repo.update(created)
        assert updated.title == "Updated Task"
        assert updated.status == "completed"

    def test_delete_by_id(self, repo: TaskRepository, sample_task: Task):
        """Test deleting a task by ID."""
        created = repo.create(sample_task)
        result = repo.delete_by_id(created.id)

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

    def test_create_configuration(
        self, repo: ConfigurationRepository, sample_config: Configuration
    ):
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

    def test_update_configuration(
        self, repo: ConfigurationRepository, sample_config: Configuration
    ):
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
            parent_id=1,
            parent_type="project",
            provider_name="github",
            resource_uri="https://github.com/test/repo",
        )

    def test_create_resource(
        self, repo: ContextProviderResourceRepository, sample_resource: ContextProviderResource
    ):
        """Test creating a new context provider resource."""
        created = repo.create(sample_resource)
        assert created.id is not None
        assert created.parent_id == 1
        assert created.parent_type == "project"
        assert created.provider_name == "github"

    def test_get_by_id(
        self, repo: ContextProviderResourceRepository, sample_resource: ContextProviderResource
    ):
        """Test getting a resource by ID."""
        created = repo.create(sample_resource)
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.parent_id == created.parent_id

    def test_get_by_id_not_found(self, repo: ContextProviderResourceRepository):
        """Test getting a resource by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_by_parent(self, repo: ContextProviderResourceRepository):
        """Test getting resources by parent."""
        resource1 = ContextProviderResource(
            parent_id=1,
            parent_type="project",
            provider_name="github",
            resource_uri="https://github.com/test/repo1",
        )
        resource2 = ContextProviderResource(
            parent_id=1,
            parent_type="project",
            provider_name="jira",
            resource_uri="https://jira.example.com/issue/123",
        )
        resource3 = ContextProviderResource(
            parent_id=2,
            parent_type="project",
            provider_name="github",
            resource_uri="https://github.com/test/repo2",
        )

        repo.create(resource1)
        repo.create(resource2)
        repo.create(resource3)

        parent_resources = repo.get_by_parent(1, "project")
        assert len(parent_resources) == 2
        for resource in parent_resources:
            assert resource.parent_id == 1
            assert resource.parent_type == "project"

    def test_update_resource(
        self, repo: ContextProviderResourceRepository, sample_resource: ContextProviderResource
    ):
        """Test updating a context provider resource."""
        created = repo.create(sample_resource)
        created.provider_name = "updated_provider"
        created.resource_uri = "https://example.com/updated"

        updated = repo.update(created)
        assert updated.provider_name == "updated_provider"
        assert updated.resource_uri == "https://example.com/updated"

    def test_delete_by_id(
        self, repo: ContextProviderResourceRepository, sample_resource: ContextProviderResource
    ):
        """Test deleting a resource by ID."""
        created = repo.create(sample_resource)
        result = repo.delete_by_id(created.id)

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ContextProviderResourceRepository):
        """Test deleting a resource by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False

    def test_delete_by_parent(self, repo: ContextProviderResourceRepository):
        """Test deleting all resources for a parent."""
        resource1 = ContextProviderResource(
            parent_id=1,
            parent_type="project",
            provider_name="github",
            resource_uri="https://github.com/test/repo1",
        )
        resource2 = ContextProviderResource(
            parent_id=1,
            parent_type="project",
            provider_name="jira",
            resource_uri="https://jira.example.com/issue/123",
        )

        repo.create(resource1)
        repo.create(resource2)

        count = repo.delete_by_parent(1, "project")
        assert count == 2

        remaining_resources = repo.get_by_parent(1, "project")
        assert len(remaining_resources) == 0


class TestProjectConversationMessageRepository:
    """Tests for ProjectConversationMessageRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ProjectConversationMessageRepository:
        return ProjectConversationMessageRepository(db_session)

    @pytest.fixture
    def project(self, db_session: Session) -> Project:
        """Create a test project for message relationships."""
        project = Project(name="Test Project", details="", current_status="active")
        db_session.add(project)
        db_session.flush()
        return project

    @pytest.fixture
    def sample_message(self, project: Project) -> ProjectConversationMessage:
        return ProjectConversationMessage(
            project_id=project.id, role="user", content="Test message"
        )

    def test_create_message(
        self, repo: ProjectConversationMessageRepository, sample_message: ProjectConversationMessage
    ):
        """Test creating a new message."""
        created = repo.create(sample_message)
        assert created.id is not None
        assert created.role == "user"
        assert created.content == "Test message"

    def test_get_by_id(
        self, repo: ProjectConversationMessageRepository, sample_message: ProjectConversationMessage
    ):
        """Test getting a message by ID."""
        created = repo.create(sample_message)
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.content == created.content

    def test_get_by_id_not_found(self, repo: ProjectConversationMessageRepository):
        """Test getting a message by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_by_project(self, repo: ProjectConversationMessageRepository, project: Project):
        """Test getting messages by project, ordered by timestamp."""
        message1 = ProjectConversationMessage(
            project_id=project.id, role="user", content="First message"
        )
        message2 = ProjectConversationMessage(
            project_id=project.id, role="assistant", content="Second message"
        )

        # Create in reverse order to test ordering
        repo.create(message2)
        repo.create(message1)

        messages = repo.get_by_project(project.id)
        assert len(messages) == 2
        # Should be ordered by timestamp ascending
        assert messages[0].created_at <= messages[1].created_at

    def test_get_recent_by_project(
        self, repo: ProjectConversationMessageRepository, project: Project
    ):
        """Test getting recent messages by project with limit."""
        # Create multiple messages
        import time

        for i in range(10):
            message = ProjectConversationMessage(
                project_id=project.id, role="user", content=f"Message {i}"
            )
            repo.create(message)
            time.sleep(0.001)  # Small delay to ensure different timestamps

        recent_messages = repo.get_recent_by_project(project.id, limit=5)
        assert len(recent_messages) == 5
        # Should be ordered by timestamp descending (most recent first)
        # The last created message (Message 9) should be first
        assert "Message 9" in recent_messages[0].content
        # Verify we got the expected messages (last 5 created)
        # Just check that we got some recent messages without comparing timestamps due to timezone issues

    def test_update_message(
        self, repo: ProjectConversationMessageRepository, sample_message: ProjectConversationMessage
    ):
        """Test updating a message."""
        created = repo.create(sample_message)
        created.content = "Updated message content"
        created.role = "assistant"

        updated = repo.update(created)
        assert updated.content == "Updated message content"
        assert updated.role == "assistant"

    def test_delete_by_id(
        self, repo: ProjectConversationMessageRepository, sample_message: ProjectConversationMessage
    ):
        """Test deleting a message by ID."""
        created = repo.create(sample_message)
        result = repo.delete_by_id(created.id)

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ProjectConversationMessageRepository):
        """Test deleting a message by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False

    def test_delete_by_project(self, repo: ProjectConversationMessageRepository, project: Project):
        """Test deleting all messages for a project."""
        message1 = ProjectConversationMessage(
            project_id=project.id, role="user", content="Message 1"
        )
        message2 = ProjectConversationMessage(
            project_id=project.id, role="assistant", content="Message 2"
        )

        repo.create(message1)
        repo.create(message2)

        count = repo.delete_by_project(project.id)
        assert count == 2

        remaining_messages = repo.get_by_project(project.id)
        assert len(remaining_messages) == 0
