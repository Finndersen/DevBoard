import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Project
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import DocumentRepository, TaskRepository
from devboard.db.repositories.project import ProjectRepository


class TestTaskRepository:
    """Tests for TaskRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> TaskRepository:
        return TaskRepository(db_session)

    @pytest.fixture
    def project(self, db_session: Session, document_repository: DocumentRepository) -> Project:
        """Create a test project for task relationships."""
        project_repo = ProjectRepository(db_session)
        spec_doc = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(name="Test Project", description="", specification=spec_doc)
        db_session.flush()
        return project

    @pytest.fixture
    def sample_task_data(self, project: Project, document_repository: DocumentRepository) -> dict:
        spec_doc = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        return {
            "title": "Test Task",
            "project_id": project.id,
            "specification": spec_doc,
            "implementation_plan": plan_doc,
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

    def test_get_all_without_filter(
        self, repo: TaskRepository, project: Project, document_repository: DocumentRepository, db_session
    ):
        """Test getting all tasks without project filter."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc1 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(project_id=project.id, title="Task 1", specification=spec_doc1, implementation_plan=plan_doc1)

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc2 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project.id,
            title="Task 2",
            specification=spec_doc2,
            implementation_plan=plan_doc2,
            status=TaskStatus.COMPLETE,
        )
        db_session.commit()

        all_tasks = repo.get_all()
        assert len(all_tasks) == 2
        task_titles = [t.title for t in all_tasks]
        assert "Task 1" in task_titles
        assert "Task 2" in task_titles

    def test_get_all_with_project_filter(
        self, repo: TaskRepository, project: Project, document_repository: DocumentRepository, db_session: Session
    ):
        """Test getting all tasks filtered by project."""
        # Create another project
        project_repo = ProjectRepository(db_session)
        spec_doc_p2 = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project2 = project_repo.create(name="Project 2", description="", specification=spec_doc_p2)
        db_session.flush()

        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc1 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(project_id=project.id, title="Task 1", specification=spec_doc1, implementation_plan=plan_doc1)

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc2 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(project_id=project2.id, title="Task 2", specification=spec_doc2, implementation_plan=plan_doc2)
        db_session.commit()

        project_tasks = repo.get_for_project(project.id)
        assert len(project_tasks) == 1
        assert project_tasks[0].title == "Task 1"
        assert project_tasks[0].project_id == project.id

    def test_get_by_project(
        self, repo: TaskRepository, project: Project, document_repository: DocumentRepository, db_session
    ):
        """Test getting tasks by project."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc1 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(project_id=project.id, title="Task 1", specification=spec_doc1, implementation_plan=plan_doc1)

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc2 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project.id,
            title="Task 2",
            specification=spec_doc2,
            implementation_plan=plan_doc2,
            status=TaskStatus.COMPLETE,
        )
        db_session.commit()

        project_tasks = repo.get_for_project(project.id)
        assert len(project_tasks) == 2
        for task in project_tasks:
            assert task.project_id == project.id

    def test_update_task(self, repo: TaskRepository, sample_task_data: dict, db_session):
        """Test updating a task."""
        created = repo.create(**sample_task_data)
        db_session.commit()
        created.title = "Updated Task"
        created.status = TaskStatus.COMPLETE

        updated = repo.update(created)
        db_session.commit()
        assert updated.title == "Updated Task"
        assert updated.status == TaskStatus.COMPLETE
