import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Project
from devboard.db.repositories import TaskRepository


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
