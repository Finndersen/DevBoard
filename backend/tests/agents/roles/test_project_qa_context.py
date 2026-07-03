"""Tests for project QA context building and TaskService.get_project_task_summaries."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from pytest import fixture

from devboard.agents.roles.project_qa import ProjectQAAgentRole, build_project_qa_context
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
        assert context.index("# Global Context") < context.index("PROJECT:")

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


def _create_initiative(
    db_session,
    parent_project_id: int,
    name: str,
    spec_content: str = "",
    complete: bool = False,
) -> Project:
    """Create an initiative (sub-project) linked to a parent project."""
    project_repo = ProjectRepository(db_session)
    document_repo = DocumentRepository(db_session)
    spec_doc = document_repo.create(
        document_type=DocumentType.INITIATIVE_CONTEXT,
        content=spec_content,
    )
    initiative = project_repo.create(
        name=name,
        description=f"{name} description",
        specification=spec_doc,
        parent_project_id=parent_project_id,
    )
    if complete:
        initiative.complete = True
    db_session.commit()
    db_session.refresh(initiative)
    return initiative


class TestBuildProjectQAContextInitiative:
    """Tests for build_project_qa_context with project hierarchy."""

    def test_initiative_context_includes_parent_project_spec(self, project_with_spec: Project, db_session):
        """Initiative context shows parent project spec and 'initiative under' framing."""
        initiative = _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Auth Initiative",
            spec_content="Initiative-specific goals here.",
        )
        db_session.refresh(initiative)

        context = build_project_qa_context(initiative, [], [])

        assert "PARENT PROJECT:" in context
        assert "Test Project" in context
        assert "This is a test project specification." in context
        assert "This is an initiative under the project above." in context
        assert "INITIATIVE:" in context
        assert "Auth Initiative" in context
        assert "Initiative-specific goals here." in context

    def test_initiative_context_includes_ids_for_tool_targeting(self, project_with_spec: Project, db_session):
        """Parent and initiative IDs appear in context so agent can target the right project."""
        initiative = _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Auth Initiative",
        )

        context = build_project_qa_context(initiative, [], [])

        assert f"(ID: {project_with_spec.id})" in context
        assert f"(ID: {initiative.id})" in context

    def test_root_project_context_has_no_parent_framing(self, project_with_spec: Project):
        """Root project context does not include parent project framing."""
        context = build_project_qa_context(project_with_spec, [], [])

        assert "PARENT PROJECT:" not in context
        assert "This is an initiative under" not in context
        assert "INITIATIVE:" not in context
        assert "PROJECT:" in context

    def test_initiative_tasks_listed_not_parent_tasks(
        self, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """Initiative agent lists only its own tasks, not the parent project's tasks."""
        initiative = _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Auth Initiative",
        )
        _create_task(db_session, project_with_spec.id, sample_codebase.id, "Parent Task", TaskStatus.PLANNING)
        initiative_task = _create_task(
            db_session, initiative.id, sample_codebase.id, "Initiative Task", TaskStatus.IMPLEMENTING
        )

        # Simulate TaskService.get_project_task_summaries called with initiative.id
        context = build_project_qa_context(initiative, [initiative_task], [])

        assert "Initiative Task" in context
        assert "Parent Task" not in context

    def test_root_project_lists_initiatives_section(self, project_with_spec: Project, db_session):
        """Root project context includes INITIATIVES section when child initiatives exist."""
        _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Initiative Alpha",
        )
        _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Initiative Beta",
            complete=True,
        )
        db_session.refresh(project_with_spec)

        context = build_project_qa_context(project_with_spec, [], [])

        assert "INITIATIVES:" in context
        assert "Initiative Alpha" in context
        assert "Initiative Beta" in context
        assert "|active|" in context
        assert "|complete|" in context

    def test_root_project_no_initiatives_section_when_empty(self, project_with_spec: Project, db_session):
        """Root project context omits INITIATIVES section when there are no child initiatives."""
        db_session.refresh(project_with_spec)

        context = build_project_qa_context(project_with_spec, [], [])

        assert "INITIATIVES:" not in context

    def test_initiative_has_no_initiatives_section(self, project_with_spec: Project, db_session):
        """Initiative context does not include an INITIATIVES section (no nesting below initiative level)."""
        initiative = _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Auth Initiative",
        )

        context = build_project_qa_context(initiative, [], [])

        assert "INITIATIVES:" not in context

    def test_initiatives_section_shows_task_counts(
        self, project_with_spec: Project, sample_codebase: Codebase, db_session
    ):
        """INITIATIVES section shows task count for each initiative."""
        initiative = _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Counted Initiative",
        )
        _create_task(db_session, initiative.id, sample_codebase.id, "Task One", TaskStatus.PLANNING)
        _create_task(db_session, initiative.id, sample_codebase.id, "Task Two", TaskStatus.IMPLEMENTING)
        db_session.refresh(project_with_spec)

        context = build_project_qa_context(project_with_spec, [], [])

        # Row format: ID|Name|Status|Tasks — task count should be 2
        assert "|Counted Initiative|active|2" in context


class TestProjectQAAgentRoleTools:
    """Tests for ProjectQAAgentRole.get_tools() — verifies tool registration by agent type."""

    def _make_role(self, project: Project, db_session) -> ProjectQAAgentRole:
        document_repo = Mock(spec=DocumentRepository)
        document_repo.db = db_session
        task_service = Mock(spec=TaskService)
        task_service.get_custom_fields.return_value = []
        return ProjectQAAgentRole(
            project=project,
            document_repository=document_repo,
            agent_config_service=Mock(),
            task_service=task_service,
            conversation_repo=Mock(),
            conversation_id=None,
        )

    def test_root_project_get_tools_no_duplicate_names(self, project_with_spec: Project, db_session):
        """Root project role registers no duplicate tool names."""
        role = self._make_role(project_with_spec, db_session)
        tools = role.get_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"

    def test_root_project_get_tools_has_document_bound_spec_tools(self, project_with_spec: Project, db_session):
        """Root project role uses document-bound spec tools (no project_id arg)."""
        role = self._make_role(project_with_spec, db_session)
        tools = role.get_tools()
        names = [t.name for t in tools]
        assert "edit_project_specification" in names
        assert "set_project_specification_content" in names

    def test_initiative_get_tools_no_duplicate_names(self, project_with_spec: Project, db_session):
        """Initiative role registers no duplicate tool names (critical: previously caused name collision)."""
        initiative = _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Test Initiative",
        )
        role = self._make_role(initiative, db_session)
        tools = role.get_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"

    def test_initiative_get_tools_has_own_context_and_parent_spec_tools(self, project_with_spec: Project, db_session):
        """Initiative role edits its own context (document-bound) and the parent project's specification."""
        initiative = _create_initiative(
            db_session,
            parent_project_id=project_with_spec.id,
            name="Test Initiative",
        )
        role = self._make_role(initiative, db_session)
        names = [t.name for t in role.get_tools()]
        # Its own initiative context document — set + edit
        assert "edit_initiative_context" in names
        assert "set_initiative_context_content" in names
        # The parent project's specification — edit only (feed outcomes upward, don't wholesale replace)
        assert "edit_project_specification" in names
        assert "set_project_specification_content" not in names
