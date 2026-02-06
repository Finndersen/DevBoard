from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Codebase, Project
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import CodebaseRepository, DocumentRepository, TaskRepository
from devboard.db.repositories.project import ProjectRepository


class TestTaskRepository:
    """Tests for TaskRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> TaskRepository:
        return TaskRepository(db_session)

    @pytest.fixture
    def codebase(self, db_session: Session) -> Codebase:
        """Create a test codebase."""
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path="/tmp/test-codebase",
        )
        codebase = codebase_repo.create(codebase)
        db_session.flush()
        return codebase

    @pytest.fixture
    def project(self, db_session: Session, document_repository: DocumentRepository) -> Project:
        """Create a test project for task relationships."""
        project_repo = ProjectRepository(db_session)
        spec_doc = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(name="Test Project", description="", specification=spec_doc)
        db_session.flush()
        return project

    @pytest.fixture
    def sample_task_data(self, project: Project, codebase: Codebase, document_repository: DocumentRepository) -> dict:
        spec_doc = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        return {
            "title": "Test Task",
            "project_id": project.id,
            "specification": spec_doc,
            "implementation_plan": plan_doc,
            "base_branch": "main",
            "codebase_id": codebase.id,
        }

    def test_create_task(self, repo: TaskRepository, sample_task_data: dict, db_session):
        """Test creating a new task."""
        created = repo.create(**sample_task_data)
        db_session.commit()
        assert created.id is not None
        assert created.title == "Test Task"
        assert created.status.value == "planning"  # Default status

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
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session,
    ):
        """Test getting all tasks without project filter."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc1 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project.id,
            title="Task 1",
            specification=spec_doc1,
            implementation_plan=plan_doc1,
            base_branch="main",
            codebase_id=codebase.id,
        )

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc2 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project.id,
            title="Task 2",
            specification=spec_doc2,
            implementation_plan=plan_doc2,
            status=TaskStatus.COMPLETE,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.commit()

        all_tasks = repo.get_all()
        assert len(all_tasks) == 2
        task_titles = [t.title for t in all_tasks]
        assert "Task 1" in task_titles
        assert "Task 2" in task_titles

    def test_get_all_with_project_filter(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test getting all tasks filtered by project."""
        # Create another project
        project_repo = ProjectRepository(db_session)
        spec_doc_p2 = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project2 = project_repo.create(name="Project 2", description="", specification=spec_doc_p2)
        db_session.flush()

        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc1 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project.id,
            title="Task 1",
            specification=spec_doc1,
            implementation_plan=plan_doc1,
            base_branch="main",
            codebase_id=codebase.id,
        )

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc2 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project2.id,
            title="Task 2",
            specification=spec_doc2,
            implementation_plan=plan_doc2,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.commit()

        project_tasks = repo.get_for_project(project.id)
        assert len(project_tasks) == 1
        assert project_tasks[0].title == "Task 1"
        assert project_tasks[0].project_id == project.id

    def test_get_by_project(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session,
    ):
        """Test getting tasks by project."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc1 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project.id,
            title="Task 1",
            specification=spec_doc1,
            implementation_plan=plan_doc1,
            base_branch="main",
            codebase_id=codebase.id,
        )

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        plan_doc2 = document_repository.create(DocumentType.TASK_IMPLEMENTATION_PLAN, "")
        repo.create(
            project_id=project.id,
            title="Task 2",
            specification=spec_doc2,
            implementation_plan=plan_doc2,
            status=TaskStatus.COMPLETE,
            base_branch="main",
            codebase_id=codebase.id,
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

    def test_get_tasks_filtered_no_filters(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered returns all tasks for project when no filters applied."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Task 1",
            specification=spec_doc1,
            base_branch="main",
            codebase_id=codebase.id,
            status=TaskStatus.PLANNING,
        )

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Task 2",
            specification=spec_doc2,
            base_branch="main",
            codebase_id=codebase.id,
            status=TaskStatus.COMPLETE,
        )
        db_session.flush()

        tasks = repo.get_tasks_filtered(project.id)

        assert len(tasks) == 2
        task_titles = {t.title for t in tasks}
        assert task_titles == {"Task 1", "Task 2"}

    def test_get_tasks_filtered_by_status(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered filters by TaskStatus."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Planning Task",
            specification=spec_doc1,
            base_branch="main",
            codebase_id=codebase.id,
            status=TaskStatus.PLANNING,
        )

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Implementing Task",
            specification=spec_doc2,
            base_branch="main",
            codebase_id=codebase.id,
            status=TaskStatus.IMPLEMENTING,
        )

        spec_doc3 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Complete Task",
            specification=spec_doc3,
            base_branch="main",
            codebase_id=codebase.id,
            status=TaskStatus.COMPLETE,
        )
        db_session.flush()

        # Filter by single status
        planning_tasks = repo.get_tasks_filtered(project.id, status_filter=[TaskStatus.PLANNING])
        assert len(planning_tasks) == 1
        assert planning_tasks[0].title == "Planning Task"

        # Filter by multiple statuses
        active_tasks = repo.get_tasks_filtered(project.id, status_filter=[TaskStatus.PLANNING, TaskStatus.IMPLEMENTING])
        assert len(active_tasks) == 2
        task_titles = {t.title for t in active_tasks}
        assert task_titles == {"Planning Task", "Implementing Task"}

    def test_get_tasks_filtered_by_created_after(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered filters by created_after date."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        task1 = repo.create(
            project_id=project.id,
            title="Old Task",
            specification=spec_doc1,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.flush()

        # Set an older created_at time
        old_time = datetime.now(UTC) - timedelta(days=10)
        task1.created_at = old_time
        db_session.flush()

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="New Task",
            specification=spec_doc2,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.flush()

        # Filter for tasks created after 5 days ago
        cutoff = datetime.now(UTC) - timedelta(days=5)
        tasks = repo.get_tasks_filtered(project.id, created_after=cutoff)

        assert len(tasks) == 1
        assert tasks[0].title == "New Task"

    def test_get_tasks_filtered_by_created_before(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered filters by created_before date."""
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        task1 = repo.create(
            project_id=project.id,
            title="Old Task",
            specification=spec_doc1,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.flush()

        # Set an older created_at time
        old_time = datetime.now(UTC) - timedelta(days=10)
        task1.created_at = old_time
        db_session.flush()

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="New Task",
            specification=spec_doc2,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.flush()

        # Filter for tasks created before 5 days ago
        cutoff = datetime.now(UTC) - timedelta(days=5)
        tasks = repo.get_tasks_filtered(project.id, created_before=cutoff)

        assert len(tasks) == 1
        assert tasks[0].title == "Old Task"

    def test_get_tasks_filtered_by_codebase_name(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered filters by codebase name."""
        # Create a second codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase2 = Codebase(
            name="Backend Codebase",
            description="Backend services",
            local_path="/tmp/backend-codebase",
        )
        codebase2 = codebase_repo.create(codebase2)
        db_session.flush()

        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Frontend Task",
            specification=spec_doc1,
            base_branch="main",
            codebase_id=codebase.id,  # "Test Codebase"
        )

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Backend Task",
            specification=spec_doc2,
            base_branch="main",
            codebase_id=codebase2.id,  # "Backend Codebase"
        )
        db_session.flush()

        # Filter by codebase name
        tasks = repo.get_tasks_filtered(project.id, codebase_name="Backend Codebase")

        assert len(tasks) == 1
        assert tasks[0].title == "Backend Task"
        assert tasks[0].codebase is not None
        assert tasks[0].codebase.name == "Backend Codebase"

    def test_get_tasks_filtered_combined_filters(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered with multiple filters combined."""
        # Create a second codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase2 = Codebase(
            name="Backend Codebase",
            description="Backend services",
            local_path="/tmp/backend-codebase",
        )
        codebase2 = codebase_repo.create(codebase2)
        db_session.flush()

        # Create tasks with different combinations of attributes
        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        task1 = repo.create(
            project_id=project.id,
            title="Old Backend Planning",
            specification=spec_doc1,
            base_branch="main",
            codebase_id=codebase2.id,
            status=TaskStatus.PLANNING,
        )
        db_session.flush()
        task1.created_at = datetime.now(UTC) - timedelta(days=10)
        db_session.flush()

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="New Backend Planning",
            specification=spec_doc2,
            base_branch="main",
            codebase_id=codebase2.id,
            status=TaskStatus.PLANNING,
        )

        spec_doc3 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="New Backend Complete",
            specification=spec_doc3,
            base_branch="main",
            codebase_id=codebase2.id,
            status=TaskStatus.COMPLETE,
        )

        spec_doc4 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="New Frontend Planning",
            specification=spec_doc4,
            base_branch="main",
            codebase_id=codebase.id,
            status=TaskStatus.PLANNING,
        )
        db_session.flush()

        # Filter: Backend codebase + Planning status + created in last 5 days
        cutoff = datetime.now(UTC) - timedelta(days=5)
        tasks = repo.get_tasks_filtered(
            project.id,
            status_filter=[TaskStatus.PLANNING],
            created_after=cutoff,
            codebase_name="Backend Codebase",
        )

        assert len(tasks) == 1
        assert tasks[0].title == "New Backend Planning"
        assert tasks[0].status == TaskStatus.PLANNING
        assert tasks[0].codebase.name == "Backend Codebase"

    def test_get_tasks_filtered_only_returns_tasks_for_specified_project(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered only returns tasks for the specified project."""
        # Create a second project
        project_repo = ProjectRepository(db_session)
        spec_doc_p2 = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project2 = project_repo.create(name="Project 2", description="", specification=spec_doc_p2)
        db_session.flush()

        spec_doc1 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Project 1 Task",
            specification=spec_doc1,
            base_branch="main",
            codebase_id=codebase.id,
        )

        spec_doc2 = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project2.id,
            title="Project 2 Task",
            specification=spec_doc2,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.flush()

        tasks = repo.get_tasks_filtered(project.id)

        assert len(tasks) == 1
        assert tasks[0].title == "Project 1 Task"
        assert tasks[0].project_id == project.id

    def test_get_tasks_filtered_eager_loads_codebase(
        self,
        repo: TaskRepository,
        project: Project,
        codebase: Codebase,
        document_repository: DocumentRepository,
        db_session: Session,
    ):
        """Test get_tasks_filtered eager loads the codebase relationship."""
        spec_doc = document_repository.create(DocumentType.TASK_SPECIFICATION, "")
        repo.create(
            project_id=project.id,
            title="Task with Codebase",
            specification=spec_doc,
            base_branch="main",
            codebase_id=codebase.id,
        )
        db_session.flush()

        tasks = repo.get_tasks_filtered(project.id)

        assert len(tasks) == 1
        # Verify codebase is loaded (accessing it should not trigger additional query)
        assert tasks[0].codebase is not None
        assert tasks[0].codebase.name == "Test Codebase"
        assert tasks[0].codebase.local_path == "/tmp/test-codebase"
