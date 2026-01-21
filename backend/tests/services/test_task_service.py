"""Tests for TaskService state transition methods."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.document import DocumentType
from devboard.db.models.task import InvalidStatusTransitionError, Task, TaskStatus
from devboard.services.task_git_service import MergeOutcome, MergeResult
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_conversation_service():
    """Mock ConversationService."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_document_repo():
    """Mock DocumentRepository."""
    repo = MagicMock()

    # Mock document creation
    def create_document(doc_type, content):
        doc = MagicMock()
        doc.id = 999
        doc.document_type = doc_type
        doc.content = content
        return doc

    repo.create.side_effect = create_document
    return repo


@pytest.fixture
def mock_task_repo():
    """Mock TaskRepository."""
    repo = MagicMock()
    repo.update.side_effect = lambda task: task  # Return the task as-is
    return repo


@pytest.fixture
def mock_worktree_slot_repo():
    """Mock WorktreeSlotRepository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def task_service(mock_conversation_service, mock_document_repo, mock_task_repo, mock_worktree_slot_repo):
    """Create TaskService instance with mocked dependencies."""
    return TaskService(
        conversation_service=mock_conversation_service,
        document_repo=mock_document_repo,
        task_repo=mock_task_repo,
        worktree_slot_repo=mock_worktree_slot_repo,
    )


@pytest.fixture
def task_in_defining():
    """Create a task in DEFINING state with specification content."""
    task = MagicMock(spec=Task)
    task.id = 1
    task.status = TaskStatus.DEFINING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = None
    task.implementation_plan_id = None
    # Mock verify_status_transition to succeed by default (no exception)
    task.verify_status_transition.return_value = None
    return task


@pytest.fixture
def task_in_defining_empty_spec():
    """Create a task in DEFINING state with empty specification."""
    task = MagicMock(spec=Task)
    task.id = 2
    task.status = TaskStatus.DEFINING
    task.specification = MagicMock()
    task.specification.content = ""
    task.implementation_plan = None
    task.implementation_plan_id = None
    return task


@pytest.fixture
def task_in_planning():
    """Create a task in PLANNING state with implementation plan content."""
    task = MagicMock(spec=Task)
    task.id = 3
    task.status = TaskStatus.PLANNING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = MagicMock()
    task.implementation_plan.content = "# Implementation Plan\n\nTest plan"
    # Mock verify_status_transition to succeed by default (no exception)
    task.verify_status_transition.return_value = None
    return task


@pytest.fixture
def task_in_planning_empty_plan():
    """Create a task in PLANNING state with empty implementation plan."""
    task = MagicMock(spec=Task)
    task.id = 4
    task.status = TaskStatus.PLANNING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = MagicMock()
    task.implementation_plan.content = ""
    return task


@pytest.fixture
def task_in_implementing():
    """Create a task in IMPLEMENTING state."""
    task = MagicMock(spec=Task)
    task.id = 5
    task.status = TaskStatus.IMPLEMENTING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = MagicMock()
    task.implementation_plan.content = "# Implementation Plan\n\nTest plan"
    return task


class TestTransitionToPlanning:
    """Tests for TaskService.transition_to_planning()."""

    def test_successful_transition(self, task_service, task_in_defining, mock_document_repo, mock_task_repo):
        """Test successful transition from DEFINING to PLANNING."""
        # Execute transition
        result = task_service.transition_to_planning(task_in_defining)

        # Verify implementation_plan document was created
        mock_document_repo.create.assert_called_once_with(DocumentType.TASK_IMPLEMENTATION_PLAN, "")

        # Verify task status was updated
        assert task_in_defining.status == TaskStatus.PLANNING

        # Verify implementation_plan was assigned
        assert task_in_defining.implementation_plan_id == 999

        # Verify task was updated in repository
        mock_task_repo.update.assert_called_once_with(task_in_defining)

        # Verify result is the updated task
        assert result == task_in_defining

    def test_transition_with_existing_plan(self, task_service, task_in_defining, mock_document_repo, mock_task_repo):
        """Test transition when implementation_plan already exists."""
        # Setup: Task already has a plan
        task_in_defining.implementation_plan = MagicMock()
        task_in_defining.implementation_plan.id = 100
        task_in_defining.implementation_plan_id = 100

        # Execute transition
        task_service.transition_to_planning(task_in_defining)

        # Verify implementation_plan document was NOT created (already exists)
        mock_document_repo.create.assert_not_called()

        # Verify task status was updated
        assert task_in_defining.status == TaskStatus.PLANNING

        # Verify task was updated in repository
        mock_task_repo.update.assert_called_once_with(task_in_defining)

    def test_transition_wrong_status(self, task_service, task_in_planning):
        """Test transition fails when task is not in DEFINING status."""
        # Mock verify_status_transition to raise exception for wrong status
        task_in_planning.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition from planning to planning"
        )

        with pytest.raises(InvalidStatusTransitionError):
            task_service.transition_to_planning(task_in_planning)

    def test_transition_empty_specification(self, task_service, task_in_defining_empty_spec):
        """Test transition fails when specification is empty."""
        # Mock verify_status_transition to raise exception for missing spec
        task_in_defining_empty_spec.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition to PLANNING without specification content"
        )

        with pytest.raises(InvalidStatusTransitionError, match="specification content"):
            task_service.transition_to_planning(task_in_defining_empty_spec)


class TestTransitionToImplementing:
    """Tests for TaskService.transition_to_implementing()."""

    def test_successful_transition(self, task_service, task_in_planning, mock_task_repo):
        """Test successful transition from PLANNING to IMPLEMENTING."""
        # Execute transition
        result = task_service.transition_to_implementing(task_in_planning)

        # Verify task status was updated
        assert task_in_planning.status == TaskStatus.IMPLEMENTING

        # Verify task was updated in repository
        mock_task_repo.update.assert_called_once_with(task_in_planning)

        # Verify result is the updated task
        assert result == task_in_planning

    def test_transition_wrong_status(self, task_service, task_in_defining):
        """Test transition fails when task is not in PLANNING status."""
        # Mock verify_status_transition to raise exception for wrong status
        task_in_defining.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition from defining to implementing"
        )

        with pytest.raises(InvalidStatusTransitionError):
            task_service.transition_to_implementing(task_in_defining)

    def test_transition_empty_plan(self, task_service, task_in_planning_empty_plan):
        """Test transition fails when implementation plan is empty."""
        # Mock verify_status_transition to raise exception for missing plan
        task_in_planning_empty_plan.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition to IMPLEMENTING without implementation plan"
        )

        with pytest.raises(InvalidStatusTransitionError, match="implementation plan"):
            task_service.transition_to_implementing(task_in_planning_empty_plan)

    def test_transition_from_implementing_fails(self, task_service, task_in_implementing):
        """Test transition fails when task is already in IMPLEMENTING status."""
        # Mock verify_status_transition to raise exception for wrong status
        task_in_implementing.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition from implementing to implementing"
        )

        with pytest.raises(InvalidStatusTransitionError):
            task_service.transition_to_implementing(task_in_implementing)


class TestTransitionValidation:
    """Tests for validation logic in transition methods."""

    def test_planning_transition_fails_for_wrong_status(self, task_service, task_in_planning, mock_document_repo):
        """Test that transition fails when task is in wrong status."""
        # Mock verify_status_transition to raise exception
        task_in_planning.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition from planning to planning"
        )

        with pytest.raises(InvalidStatusTransitionError):
            task_service.transition_to_planning(task_in_planning)

        # Verify verify_status_transition was called
        task_in_planning.verify_status_transition.assert_called_once_with(TaskStatus.PLANNING)

    def test_implementing_transition_fails_for_wrong_status(self, task_service, task_in_defining, mock_task_repo):
        """Test that transition fails when task is in wrong status."""
        # Mock verify_status_transition to raise exception
        task_in_defining.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition from defining to implementing"
        )

        with pytest.raises(InvalidStatusTransitionError):
            task_service.transition_to_implementing(task_in_defining)

        # Verify verify_status_transition was called
        task_in_defining.verify_status_transition.assert_called_once_with(TaskStatus.IMPLEMENTING)


class TestCompleteTaskWithLocalMerge:
    """Tests for TaskService.complete_task_with_local_merge()."""

    @pytest.fixture
    def task_with_branch(self):
        """Create a task in IMPLEMENTING state with branch configured."""
        task = MagicMock(spec=Task)
        task.id = 10
        task.status = TaskStatus.IMPLEMENTING
        task.branch_name = "feature/test-branch"
        task.base_branch = "main"
        task.change_summary = None
        task.change_summary_id = None
        task.codebase = MagicMock()
        task.codebase.merge_method = MergeMethod.SQUASH
        task.verify_status_transition.return_value = None
        return task

    @pytest.mark.asyncio
    async def test_succeeds_with_merge_success(
        self, task_service, task_with_branch, mock_document_repo, mock_task_repo
    ):
        """Test complete succeeds when merge returns SUCCESS outcome."""
        mock_merge_result = MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=MergeMethod.SQUASH,
            message="Squash merged feature branch into main",
            merge_commit="abc123",
        )

        with patch("devboard.services.task_service.TaskGitService") as MockTaskGitService:
            mock_git_service = MagicMock()
            mock_git_service.merge_task_feature_branch = AsyncMock(return_value=mock_merge_result)
            MockTaskGitService.return_value = mock_git_service

            result = await task_service.complete_task_with_local_merge(task_with_branch, "Changes summary")

        assert result.outcome == MergeOutcome.SUCCESS
        assert task_with_branch.status == TaskStatus.COMPLETE
        mock_document_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_succeeds_with_merge_skipped(
        self, task_service, task_with_branch, mock_document_repo, mock_task_repo
    ):
        """Test complete succeeds when merge returns SKIPPED outcome (already merged)."""
        mock_merge_result = MergeResult(
            outcome=MergeOutcome.SKIPPED,
            merge_method=MergeMethod.SQUASH,
            message="Branch has no new commits - already merged",
        )

        with patch("devboard.services.task_service.TaskGitService") as MockTaskGitService:
            mock_git_service = MagicMock()
            mock_git_service.merge_task_feature_branch = AsyncMock(return_value=mock_merge_result)
            MockTaskGitService.return_value = mock_git_service

            result = await task_service.complete_task_with_local_merge(task_with_branch, "Changes summary")

        assert result.outcome == MergeOutcome.SKIPPED
        assert task_with_branch.status == TaskStatus.COMPLETE
        mock_document_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_fails_with_merge_conflict(self, task_service, task_with_branch, mock_document_repo):
        """Test complete raises ValueError when merge returns CONFLICT outcome."""
        mock_merge_result = MergeResult(
            outcome=MergeOutcome.CONFLICT,
            merge_method=MergeMethod.SQUASH,
            message="Conflicts detected between feature and main",
        )

        with patch("devboard.services.task_service.TaskGitService") as MockTaskGitService:
            mock_git_service = MagicMock()
            mock_git_service.merge_task_feature_branch = AsyncMock(return_value=mock_merge_result)
            MockTaskGitService.return_value = mock_git_service

            with pytest.raises(ValueError, match="Merge failed"):
                await task_service.complete_task_with_local_merge(task_with_branch, "Changes summary")

    @pytest.mark.asyncio
    async def test_fails_with_merge_error(self, task_service, task_with_branch, mock_document_repo):
        """Test complete raises ValueError when merge returns ERROR outcome."""
        mock_merge_result = MergeResult(
            outcome=MergeOutcome.ERROR,
            merge_method=MergeMethod.SQUASH,
            message="Git command failed",
        )

        with patch("devboard.services.task_service.TaskGitService") as MockTaskGitService:
            mock_git_service = MagicMock()
            mock_git_service.merge_task_feature_branch = AsyncMock(return_value=mock_merge_result)
            MockTaskGitService.return_value = mock_git_service

            with pytest.raises(ValueError, match="Merge failed"):
                await task_service.complete_task_with_local_merge(task_with_branch, "Changes summary")

    @pytest.mark.asyncio
    async def test_fails_without_branch_configured(self, task_service, task_with_branch):
        """Test complete raises ValueError when task has no branch."""
        task_with_branch.branch_name = None

        with pytest.raises(ValueError, match="has no branch configured"):
            await task_service.complete_task_with_local_merge(task_with_branch, "Changes summary")
