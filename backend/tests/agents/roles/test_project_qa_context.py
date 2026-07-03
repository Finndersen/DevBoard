"""Tests for project QA context building and TaskService.get_project_task_summaries."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from pytest import fixture

from devboard.agents.roles.project_qa import build_project_qa_context
from devboard.db.models import DocumentType, Project, Task
from devboard.db.models.codebase import Codebase
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import CodebaseRepository, DocumentRepository, ProjectRepository, TaskRepository
from devboard.db.repositories.custom_field import CustomFieldRepository
from devboard.services.conversation_service import ConversationService
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_service import RECENT_COMPLETED_TASKS_LIMIT, TaskService


@fixture
def sample_codebase(db_session) -> Codebase:
    """Create a sample codebase for testing."""
    codebase_repo = CodebaseRepository(db_session)
    codebase = Codebase(
        name="Test Codebase",
        description="A test codebase",
        local_path="/tmp/test-codebase",
    )
    codebase = codebase_repo.create(codebase)
    db_session.commit()
    db_session.refresh(codebase)
    return codebase


@fixture
def project_with_spec(db_session) -> Project:
    """Create a project with specification document."""
    project_repo = ProjectRepository(db_session)
    document_repo = DocumentRepository(db_session)

    spec_doc = document_repo.create(
        document_type=DocumentType.PROJECT_SPECIFICATION,
        content="# Test Project\n\nThis is a test project specification.",
    )

    project = project_repo.create(
        name="Test Project",
        description="A test project",
        specification=spec_doc,
    )

    db_session.commit()
    db_session.refresh(project)
    return project


@fixture
def task_service(db_session) -> TaskService:
    """TaskService with real repositories and mocked unused dependencies."""
    return TaskService(
        conversation_service=Mock(spec=ConversationService),
        document_repo=DocumentRepository(db_session),
        task_repo=TaskRepository(db_session),
        custom_field_repo=Mock(spec=CustomFieldRepository),
        system_event_emitter=Mock(spec=SystemEventEmitter),
    )


def _create_task(
    db_session,
    project_id: int,
    codebase_id: int,
    title: str,
    status: TaskStatus,
    updated_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Task:
    """Create a task in the DB with optional timestamp overrides."""
    task_repo = TaskRepository(db_session)
    document_repo = DocumentRepository(db_session)

    spec_doc = document_repo.create(
        document_type=DocumentType.TASK_SPECIFICATION,
        content="",
    )

    task = task_repo.create(
        project_id=project_id,
        title=title,
        status=status,
        specification=spec_doc,
        implementation_plan=None,
        base_branch="main",
        branch_name=f"feature/{title.lower().replace(' ', '-')}",
        codebase_id=codebase_id,
    )

    if updated_at is not None:
        task.updated_at = updated_at
    if created_at is not None:
        task.created_at = created_at

    db_session.commit()
    db_session.refresh(task)
    return task


class TestBuildProjectQAContext:
    """Tests for build_project_qa_context function."""

    def test_no_tasks_includes_project_spec_only(self, project_with_spec: Project):
        """Context includes project name and spec but no task sections when no tasks."""
        context = build_project_qa_context(project_with_spec, [], [])

        assert "Test Project" in context
        assert "This is a test project specification." in context
        assert "ACTIVE TASKS:" not in context
        assert "RECENTLY COMPLETED TASKS:" not in context

    def test_active_tasks_section(self, project_with_spec: Project, sample_codebase: Codebase, db_session):
        """Active tasks appear in ACTIVE TASKS section with no completed section."""
        task = _create_task(
            db_session,
            project_id=project_with_spec.id,
            codebase_id=sample_codebase.id,
            title="Add user authentication",
            status=TaskStatus.PLANNING,
            created_at=datetime(2026, 3, 10, tzinfo=UTC),
            updated_at=datetime(2026, 3, 15, tzinfo=UTC),
        )

        context = build_project_qa_context(project_with_spec, [task], [])

        assert "ACTIVE TASKS:" in context
        assert f"{task.id}|planning|Add user authentication|2026-03-10" in context
        assert "RECENTLY COMPLETED TASKS:" not in context

    def test_recently_completed_tasks_section(self, project_with_spec: Project, sample_codebase: Codebase, db_session):
        """Completed tasks appear in RECENTLY COMPLETED TASKS section with no active section."""
        task = _create_task(
            db_session,
            project_id=project_with_spec.id,
            codebase_id=sample_codebase.id,
            title="Setup CI pipeline",
            status=TaskStatus.COMPLETE,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
            updated_at=datetime(2026, 3, 9, tzinfo=UTC),
        )

        context = build_project_qa_context(project_with_spec, [], [task])

        assert "RECENTLY COMPLETED TASKS:" in context
        assert f"{task.id}|complete|Setup CI pipeline|2026-03-01" in context
        assert "ACTIVE TASKS:" not in context

    def test_both_active_and_completed_sections(
        self, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """Both sections appear when both active and completed tasks are provided."""
        active_task = _create_task(
            db_session,
            project_id=project_with_spec.id,
            codebase_id=sample_codebase.id,
            title="Fix pagination bug",
            status=TaskStatus.IMPLEMENTING,
            created_at=datetime(2026, 3, 12, tzinfo=UTC),
            updated_at=datetime(2026, 3, 16, tzinfo=UTC),
        )
        completed_task = _create_task(
            db_session,
            project_id=project_with_spec.id,
            codebase_id=sample_codebase.id,
            title="Setup CI pipeline",
            status=TaskStatus.COMPLETE,
            created_at=datetime(2026, 3, 1, tzinfo=UTC),
            updated_at=datetime(2026, 3, 9, tzinfo=UTC),
        )

        context = build_project_qa_context(project_with_spec, [active_task], [completed_task])

        assert "ACTIVE TASKS:" in context
        assert "RECENTLY COMPLETED TASKS:" in context
        assert "|implementing|" in context
        assert "|complete|" in context

    def test_date_format_no_time_component(self, project_with_spec: Project, sample_codebase: Codebase, db_session):
        """Dates formatted as YYYY-MM-DD with no time component."""
        task = _create_task(
            db_session,
            project_id=project_with_spec.id,
            codebase_id=sample_codebase.id,
            title="Test Task",
            status=TaskStatus.PLANNING,
            created_at=datetime(2026, 3, 10, 14, 30, 45, tzinfo=UTC),
            updated_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
        )

        context = build_project_qa_context(project_with_spec, [task], [])

        assert "2026-03-10" in context
        assert "14:30" not in context

    def test_row_format(self, project_with_spec: Project, sample_codebase: Codebase, db_session):
        """Task table includes header row and pipe-delimited data rows."""
        task = _create_task(
            db_session,
            project_id=project_with_spec.id,
            codebase_id=sample_codebase.id,
            title="Add user authentication",
            status=TaskStatus.PR_OPEN,
            created_at=datetime(2026, 3, 10, tzinfo=UTC),
            updated_at=datetime(2026, 3, 15, tzinfo=UTC),
        )

        context = build_project_qa_context(project_with_spec, [task], [])

        assert "ID|Status|Title|Created" in context
        assert f"{task.id}|pr_open|Add user authentication|2026-03-10" in context

    def test_global_context_prepended_when_provided(self, project_with_spec: Project):
        """Non-empty global context appears before project name and spec."""
        gc = "Platform: Internal developer tooling."
        context = build_project_qa_context(project_with_spec, [], [], global_context=gc)

        assert "# Global Context" in context
        assert gc in context
        assert context.index("# Global Context") < context.index("PROJECT NAME:")

    def test_global_context_omitted_when_none(self, project_with_spec: Project):
        """No global context section when global_context is None."""
        context = build_project_qa_context(project_with_spec, [], [], global_context=None)

        assert "# Global Context" not in context

    def test_global_context_omitted_when_empty_string(self, project_with_spec: Project):
        """No global context section when global_context is empty string."""
        context = build_project_qa_context(project_with_spec, [], [], global_context="")

        assert "# Global Context" not in context


class TestGetProjectTaskSummaries:
    """Tests for TaskService.get_project_task_summaries."""

    def test_splits_active_and_completed_correctly(
        self, task_service: TaskService, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """planning/implementing/pr_open tasks go to active; COMPLETE goes to completed."""
        planning = _create_task(db_session, project_with_spec.id, sample_codebase.id, "Planning", TaskStatus.PLANNING)
        implementing = _create_task(
            db_session, project_with_spec.id, sample_codebase.id, "Implementing", TaskStatus.IMPLEMENTING
        )
        pr_open = _create_task(db_session, project_with_spec.id, sample_codebase.id, "PR Open", TaskStatus.PR_OPEN)
        complete = _create_task(db_session, project_with_spec.id, sample_codebase.id, "Complete", TaskStatus.COMPLETE)

        active, completed = task_service.get_project_task_summaries(project_with_spec.id)

        active_ids = {t.id for t in active}
        completed_ids = {t.id for t in completed}

        assert planning.id in active_ids
        assert implementing.id in active_ids
        assert pr_open.id in active_ids
        assert complete.id in completed_ids
        assert complete.id not in active_ids

    def test_limits_completed_to_recent_n(
        self, task_service: TaskService, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """Only returns RECENT_COMPLETED_TASKS_LIMIT most recent completed tasks."""
        now = datetime(2026, 3, 16, tzinfo=UTC)
        for i in range(8):
            _create_task(
                db_session,
                project_with_spec.id,
                sample_codebase.id,
                f"Complete Task {i}",
                TaskStatus.COMPLETE,
                updated_at=now - timedelta(days=i),
            )

        _, completed = task_service.get_project_task_summaries(project_with_spec.id)

        assert len(completed) == RECENT_COMPLETED_TASKS_LIMIT

    def test_completed_sorted_by_updated_at_descending(
        self, task_service: TaskService, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """Completed tasks returned sorted by updated_at descending."""
        now = datetime(2026, 3, 16, tzinfo=UTC)
        oldest = _create_task(
            db_session,
            project_with_spec.id,
            sample_codebase.id,
            "Oldest",
            TaskStatus.COMPLETE,
            updated_at=now - timedelta(days=10),
        )
        newest = _create_task(
            db_session,
            project_with_spec.id,
            sample_codebase.id,
            "Newest",
            TaskStatus.COMPLETE,
            updated_at=now - timedelta(days=1),
        )
        middle = _create_task(
            db_session,
            project_with_spec.id,
            sample_codebase.id,
            "Middle",
            TaskStatus.COMPLETE,
            updated_at=now - timedelta(days=5),
        )

        _, completed = task_service.get_project_task_summaries(project_with_spec.id)

        assert completed[0].id == newest.id
        assert completed[1].id == middle.id
        assert completed[2].id == oldest.id

    def test_active_sorted_by_updated_at_descending(
        self, task_service: TaskService, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """Active tasks returned sorted by updated_at descending."""
        now = datetime(2026, 3, 16, tzinfo=UTC)
        older = _create_task(
            db_session,
            project_with_spec.id,
            sample_codebase.id,
            "Older",
            TaskStatus.PLANNING,
            updated_at=now - timedelta(days=5),
        )
        newer = _create_task(
            db_session,
            project_with_spec.id,
            sample_codebase.id,
            "Newer",
            TaskStatus.IMPLEMENTING,
            updated_at=now - timedelta(days=1),
        )

        active, _ = task_service.get_project_task_summaries(project_with_spec.id)

        assert active[0].id == newer.id
        assert active[1].id == older.id

    def test_project_isolation(
        self, task_service: TaskService, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """Tasks from other projects are excluded."""
        document_repo = DocumentRepository(db_session)
        project_repo = ProjectRepository(db_session)
        other_spec = document_repo.create(DocumentType.PROJECT_SPECIFICATION, "Other")
        other_project = project_repo.create(name="Other", description="", specification=other_spec)
        db_session.commit()

        our_task = _create_task(db_session, project_with_spec.id, sample_codebase.id, "Our Task", TaskStatus.PLANNING)
        other_task = _create_task(db_session, other_project.id, sample_codebase.id, "Other Task", TaskStatus.PLANNING)

        active, _ = task_service.get_project_task_summaries(project_with_spec.id)

        active_ids = {t.id for t in active}
        assert our_task.id in active_ids
        assert other_task.id not in active_ids
