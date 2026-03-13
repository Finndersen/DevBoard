"""Tests for task context builder functions."""

from pytest import fixture

from devboard.agents.roles.context_helpers import build_task_context as build_task_planning_context
from devboard.db.models import Codebase, DocumentType, Project, Task
from devboard.db.models.task import TaskStatus
from devboard.db.models.worktree_slot import WorktreeSlot
from devboard.db.repositories import CodebaseRepository, DocumentRepository, ProjectRepository, TaskRepository


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

    # Create specification document
    spec_doc = document_repo.create(
        document_type=DocumentType.PROJECT_SPECIFICATION,
        content="# Test Project\n\nThis is a test project specification.",
    )

    # Create project
    project = project_repo.create(
        name="Test Project",
        description="A test project",
        specification=spec_doc,
    )

    db_session.commit()
    db_session.refresh(project)
    return project


@fixture
def task_with_documents(db_session, project_with_spec: Project, sample_codebase: Codebase) -> Task:
    """Create a task with specification and implementation plan documents."""
    task_repo = TaskRepository(db_session)
    document_repo = DocumentRepository(db_session)

    # Create task specification document
    spec_doc = document_repo.create(
        document_type=DocumentType.TASK_SPECIFICATION,
        content="## Task Goal\n\nImplement feature X",
    )

    # Create task implementation plan document
    impl_doc = document_repo.create(
        document_type=DocumentType.TASK_IMPLEMENTATION_PLAN,
        content="## Implementation Steps\n\n1. Step one\n2. Step two",
    )

    # Create task
    task = task_repo.create(
        project_id=project_with_spec.id,
        title="Test Task",
        status=TaskStatus.PLANNING,
        specification=spec_doc,
        implementation_plan=impl_doc,
        base_branch="main",
        branch_name="feature/test-task",
        codebase_id=sample_codebase.id,
    )

    # Create a worktree slot for the task
    worktree_slot = WorktreeSlot(
        codebase_id=sample_codebase.id,
        path="/tmp/test-codebase",
        is_main_repo=True,
        locked=True,
        last_used_by_task_id=task.id,
    )
    db_session.add(worktree_slot)

    db_session.commit()
    db_session.refresh(task)
    return task


@fixture
def task_without_implementation_plan(db_session, project_with_spec: Project, sample_codebase: Codebase) -> Task:
    """Create a task with specification but no implementation plan."""
    task_repo = TaskRepository(db_session)
    document_repo = DocumentRepository(db_session)

    # Create task specification document
    spec_doc = document_repo.create(
        document_type=DocumentType.TASK_SPECIFICATION,
        content="## Task Goal\n\nImplement feature X",
    )

    # Create task without implementation plan
    task = task_repo.create(
        project_id=project_with_spec.id,
        title="Test Task",
        status=TaskStatus.PLANNING,
        specification=spec_doc,
        implementation_plan=None,
        base_branch="main",
        branch_name="feature/test-task",
        codebase_id=sample_codebase.id,
    )

    # Create a worktree slot for the task
    worktree_slot = WorktreeSlot(
        codebase_id=sample_codebase.id,
        path="/tmp/test-codebase",
        is_main_repo=True,
        locked=True,
        last_used_by_task_id=task.id,
    )
    db_session.add(worktree_slot)

    db_session.commit()
    db_session.refresh(task)
    return task


class TestBuildTaskPlanningContext:
    """Tests for build_task_planning_context function."""

    def test_builds_context_with_all_documents(self, task_with_documents: Task):
        """Test that context includes all required documents when implementation plan exists."""
        context = build_task_planning_context(task_with_documents)

        # Check task metadata
        assert f"ID: {task_with_documents.id}" in context
        assert "NAME: Test Task" in context
        assert "STATUS: planning" in context

        # Check project specification is included
        assert "PROJECT SPECIFICATION:" in context
        assert "This is a test project specification." in context

        # Check task specification is included
        assert "TASK SPECIFICATION:" in context
        assert "Implement feature X" in context

        # Check implementation plan is included
        assert "IMPLEMENTATION PLAN:" in context
        assert "Implementation Steps" in context

    def test_builds_context_without_implementation_plan(self, task_without_implementation_plan: Task):
        """Test that context excludes implementation plan section when it doesn't exist."""
        context = build_task_planning_context(task_without_implementation_plan)

        # Check task metadata
        assert f"ID: {task_without_implementation_plan.id}" in context
        assert "NAME: Test Task" in context
        assert "STATUS: planning" in context

        # Check project specification is included
        assert "PROJECT SPECIFICATION:" in context
        assert "This is a test project specification." in context

        # Check task specification is included
        assert "TASK SPECIFICATION:" in context
        assert "Implement feature X" in context

        # Implementation plan should NOT be included
        assert "IMPLEMENTATION PLAN:" not in context

    def test_handles_empty_documents(self, db_session, project_with_spec: Project, sample_codebase: Codebase):
        """Test that empty documents show <EMPTY>."""
        task_repo = TaskRepository(db_session)
        document_repo = DocumentRepository(db_session)

        # Create empty documents
        spec_doc = document_repo.create(
            document_type=DocumentType.TASK_SPECIFICATION,
            content="",
        )

        impl_doc = document_repo.create(
            document_type=DocumentType.TASK_IMPLEMENTATION_PLAN,
            content="",
        )

        task = task_repo.create(
            project_id=project_with_spec.id,
            title="Empty Task",
            status=TaskStatus.PLANNING,
            specification=spec_doc,
            implementation_plan=impl_doc,
            base_branch="main",
            branch_name="feature/test-task",
            codebase_id=sample_codebase.id,
        )

        # Create a worktree slot for the task
        worktree_slot = WorktreeSlot(
            codebase_id=sample_codebase.id,
            path="/tmp/test-codebase",
            is_main_repo=True,
            locked=True,
            last_used_by_task_id=task.id,
        )
        db_session.add(worktree_slot)

        db_session.commit()
        db_session.refresh(task)

        context = build_task_planning_context(task)

        # Should have <EMPTY> for both task documents (but not project spec)
        assert context.count("<EMPTY>") == 2

    def test_handles_empty_task_specification(self, db_session, project_with_spec: Project, sample_codebase: Codebase):
        """Test that empty task specification shows <EMPTY>."""
        task_repo = TaskRepository(db_session)
        document_repo = DocumentRepository(db_session)

        # Create empty specification document
        spec_doc = document_repo.create(
            document_type=DocumentType.TASK_SPECIFICATION,
            content="",
        )

        task = task_repo.create(
            project_id=project_with_spec.id,
            title="Empty Task",
            status=TaskStatus.PLANNING,
            specification=spec_doc,
            implementation_plan=None,
            base_branch="main",
            branch_name="feature/test-task",
            codebase_id=sample_codebase.id,
        )

        # Create a worktree slot for the task
        worktree_slot = WorktreeSlot(
            codebase_id=sample_codebase.id,
            path="/tmp/test-codebase",
            is_main_repo=True,
            locked=True,
            last_used_by_task_id=task.id,
        )
        db_session.add(worktree_slot)

        db_session.commit()
        db_session.refresh(task)

        context = build_task_planning_context(task)

        assert "<EMPTY>" in context
        # Implementation plan section should not be present (no plan exists)
        assert "IMPLEMENTATION PLAN:" not in context

    def test_handles_empty_project_specification(self, db_session, sample_codebase: Codebase):
        """Test that empty project specification shows <EMPTY>."""
        project_repo = ProjectRepository(db_session)
        task_repo = TaskRepository(db_session)
        document_repo = DocumentRepository(db_session)

        # Create project with empty specification
        project_spec_doc = document_repo.create(
            document_type=DocumentType.PROJECT_SPECIFICATION,
            content="",
        )

        project = project_repo.create(
            name="Empty Project",
            description="Project with empty spec",
            specification=project_spec_doc,
        )

        # Create task
        spec_doc = document_repo.create(
            document_type=DocumentType.TASK_SPECIFICATION,
            content="Task content",
        )

        task = task_repo.create(
            project_id=project.id,
            title="Test Task",
            status=TaskStatus.PLANNING,
            specification=spec_doc,
            implementation_plan=None,
            base_branch="main",
            branch_name="feature/test-task",
            codebase_id=sample_codebase.id,
        )

        # Create a worktree slot for the task
        worktree_slot = WorktreeSlot(
            codebase_id=sample_codebase.id,
            path="/tmp/test-codebase",
            is_main_repo=True,
            locked=True,
            last_used_by_task_id=task.id,
        )
        db_session.add(worktree_slot)

        db_session.commit()
        db_session.refresh(task)

        context = build_task_planning_context(task)

        # Should show <EMPTY> for project spec
        assert "PROJECT SPECIFICATION:" in context
        assert context.count("<EMPTY>") == 1

    def test_lazy_loads_project_relationship(self, db_session, project_with_spec: Project, sample_codebase: Codebase):
        """Test that project relationship is lazy loaded when needed."""
        task_repo = TaskRepository(db_session)
        document_repo = DocumentRepository(db_session)

        spec_doc = document_repo.create(
            document_type=DocumentType.TASK_SPECIFICATION,
            content="Test content",
        )

        impl_doc = document_repo.create(
            document_type=DocumentType.TASK_IMPLEMENTATION_PLAN,
            content="Test plan",
        )

        task = task_repo.create(
            project_id=project_with_spec.id,
            title="Test Task",
            status=TaskStatus.PLANNING,
            specification=spec_doc,
            implementation_plan=impl_doc,
            base_branch="main",
            branch_name="feature/test-task",
            codebase_id=sample_codebase.id,
        )

        # Create a worktree slot for the task
        worktree_slot = WorktreeSlot(
            codebase_id=sample_codebase.id,
            path="/tmp/test-codebase",
            is_main_repo=True,
            locked=True,
            last_used_by_task_id=task.id,
        )
        db_session.add(worktree_slot)

        db_session.commit()
        db_session.refresh(task)

        # Access context - should trigger lazy load of project
        context = build_task_planning_context(task)

        # Verify project specification was loaded
        assert "This is a test project specification." in context
