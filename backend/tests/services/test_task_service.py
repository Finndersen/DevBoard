"""Tests for TaskService state transition methods."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.db.models.codebase import MergeMethod
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
def mock_custom_field_repo():
    """Mock CustomFieldRepository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def task_service(mock_conversation_service, mock_document_repo, mock_task_repo, mock_custom_field_repo):
    """Create TaskService instance with mocked dependencies."""
    return TaskService(
        conversation_service=mock_conversation_service,
        document_repo=mock_document_repo,
        task_repo=mock_task_repo,
        custom_field_repo=mock_custom_field_repo,
    )


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
def task_in_planning_no_plan():
    """Create a task in PLANNING state with no implementation plan."""
    task = MagicMock(spec=Task)
    task.id = 6
    task.status = TaskStatus.PLANNING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = None
    task.implementation_plan_id = None
    task.implementation_plan_structured = None
    # Mock verify_status_transition to succeed by default (no exception)
    task.verify_status_transition.return_value = None
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

    def test_transition_wrong_status(self, task_service, task_in_implementing):
        """Test transition fails when task is not in PLANNING status."""
        # Mock verify_status_transition to raise exception for wrong status
        task_in_implementing.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition from implementing to implementing"
        )

        with pytest.raises(InvalidStatusTransitionError):
            task_service.transition_to_implementing(task_in_implementing)

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

    def test_transition_updates_updated_at(self, task_service, task_in_planning, mock_task_repo):
        """Test that transition_to_implementing updates updated_at."""
        old_time = datetime.now(UTC) - timedelta(hours=1)
        task_in_planning.created_at = old_time
        task_in_planning.updated_at = old_time

        task_service.transition_to_implementing(task_in_planning)

        assert task_in_planning.updated_at > old_time


class TestTransitionToPrOpen:
    """Tests for TaskService.transition_to_pr_open()."""

    @pytest.fixture
    def task_in_implementing_for_pr(self):
        task = MagicMock(spec=Task)
        task.id = 7
        task.status = TaskStatus.IMPLEMENTING
        task.verify_status_transition.return_value = None
        return task

    def test_transition_updates_updated_at(self, task_service, task_in_implementing_for_pr, mock_task_repo):
        """Test that transition_to_pr_open updates updated_at."""
        old_time = datetime.now(UTC) - timedelta(hours=1)
        task_in_implementing_for_pr.updated_at = old_time

        task_service.transition_to_pr_open(task_in_implementing_for_pr, pr_number=42)

        assert task_in_implementing_for_pr.updated_at > old_time


class TestTransitionToComplete:
    """Tests for TaskService.transition_to_complete()."""

    @pytest.fixture
    def task_in_pr_open(self):
        task = MagicMock(spec=Task)
        task.id = 8
        task.status = TaskStatus.PR_OPEN
        task.verify_status_transition.return_value = None
        return task

    def test_transition_updates_updated_at(self, task_service, task_in_pr_open, mock_task_repo):
        """Test that transition_to_complete updates updated_at."""
        old_time = datetime.now(UTC) - timedelta(hours=1)
        task_in_pr_open.updated_at = old_time

        task_service.transition_to_complete(task_in_pr_open)

        assert task_in_pr_open.updated_at > old_time


class TestTransitionValidation:
    """Tests for validation logic in transition methods."""

    def test_implementing_transition_validates_status_before_prerequisites(
        self, task_service, task_in_planning_no_plan, mock_task_repo
    ):
        """Test that status check happens before prerequisite validation."""
        # Change status to IMPLEMENTING (wrong status for this transition)
        task_in_planning_no_plan.status = TaskStatus.IMPLEMENTING

        # Mock verify_status_transition to raise exception for wrong status
        task_in_planning_no_plan.verify_status_transition.side_effect = InvalidStatusTransitionError(
            "Cannot transition from implementing to implementing"
        )

        # Should fail with status error
        with pytest.raises(InvalidStatusTransitionError):
            task_service.transition_to_implementing(task_in_planning_no_plan)


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

        mock_document_repo.create.assert_not_called()

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

        mock_document_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_fails_without_branch_configured(self, task_service, task_with_branch):
        """Test complete raises ValueError when task has no branch."""
        task_with_branch.branch_name = None

        with pytest.raises(ValueError, match="has no branch configured"):
            await task_service.complete_task_with_local_merge(task_with_branch, "Changes summary")


class TestUpdateTask:
    """Tests for TaskService.update_task()."""

    @pytest.fixture
    def task(self):
        task = MagicMock(spec=Task)
        task.id = 1
        task.title = "Original Title"
        task.custom_fields = {"a": 1}
        return task

    def test_update_task_title(self, task_service, task, mock_task_repo):
        """Updates task title when provided."""
        result = task_service.update_task(task, title="New Title")

        assert task.title == "New Title"
        mock_task_repo.update.assert_called_once_with(task)
        assert result == task

    def test_update_task_custom_fields_merge(self, task_service, task, mock_task_repo):
        """Merges provided custom_fields into existing ones."""
        task.custom_fields = {"a": 1}

        task_service.update_task(task, custom_fields={"b": 2})

        assert task.custom_fields == {"a": 1, "b": 2}

    def test_update_task_custom_fields_remove_null(self, task_service, task, mock_task_repo):
        """Removes keys set to None from custom_fields."""
        task.custom_fields = {"a": 1, "b": 2}

        task_service.update_task(task, custom_fields={"a": None})

        assert task.custom_fields == {"b": 2}

    def test_update_task_custom_fields_from_none(self, task_service, task, mock_task_repo):
        """Handles existing custom_fields being None."""
        task.custom_fields = None

        task_service.update_task(task, custom_fields={"a": 1})

        assert task.custom_fields == {"a": 1}

    def test_update_task_no_changes(self, task_service, task, mock_task_repo):
        """Calls update even when no fields change."""
        task_service.update_task(task)

        assert task.title == "Original Title"
        assert task.custom_fields == {"a": 1}
        mock_task_repo.update.assert_called_once_with(task)

    def test_update_task_refreshes_updated_at(self, task_service, task, mock_task_repo):
        """update_task sets updated_at to a time later than the original."""
        old_time = datetime.now(UTC) - timedelta(hours=1)
        task.updated_at = old_time

        task_service.update_task(task, title="New Title")

        assert task.updated_at > old_time
