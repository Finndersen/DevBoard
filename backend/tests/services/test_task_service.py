"""Tests for TaskService state transition methods."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.codebase import MergeMethod
from devboard.db.models.task import InvalidStatusTransitionError, Task, TaskStatus
from devboard.services.system_event_emitter import SystemEventEmitter
from devboard.services.task_git.types import MergeFailureError, TaskConfigurationError
from devboard.services.task_git_service import MergeOutcome, MergeResult
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_conversation_service():
    """Mock ConversationService."""
    service = MagicMock()
    # replace_active_conversation returns a Conversation-like object with an id
    mock_new_conv = MagicMock()
    mock_new_conv.id = 100
    service.replace_active_conversation.return_value = mock_new_conv
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
def mock_system_event_emitter():
    """Mock SystemEventEmitter."""
    return MagicMock(spec=SystemEventEmitter)


@pytest.fixture
def task_service(
    mock_conversation_service, mock_document_repo, mock_task_repo, mock_custom_field_repo, mock_system_event_emitter
):
    """Create TaskService instance with mocked dependencies."""
    return TaskService(
        conversation_service=mock_conversation_service,
        document_repo=mock_document_repo,
        task_repo=mock_task_repo,
        custom_field_repo=mock_custom_field_repo,
        system_event_emitter=mock_system_event_emitter,
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


class TestCreateTask:
    """Tests for TaskService.create_task()."""

    @pytest.mark.asyncio
    async def test_create_task_basic(self, task_service, mock_task_repo, mock_document_repo, mock_conversation_service):
        """Creates task with auto-generated branch name and calls git branch creation."""
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task_repo.create.return_value = mock_task
        mock_custom_field_repo = task_service.custom_field_repo
        mock_custom_field_repo.get_mandatory_fields.return_value = []

        with patch(
            "devboard.services.task_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ) as mock_create_branch:
            result = await task_service.create_task(
                project_id=1,
                title="My New Task",
                base_branch="main",
                codebase_id=10,
            )

        mock_create_branch.assert_called_once_with(mock_task)
        mock_conversation_service.create_initial_conversation_for_parent_entity.assert_called_once()
        assert result is mock_task

    @pytest.mark.asyncio
    async def test_create_task_auto_generates_branch_name(self, task_service, mock_task_repo):
        """Auto-generates branch name from title when not provided."""
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task_repo.create.return_value = mock_task
        task_service.custom_field_repo.get_mandatory_fields.return_value = []

        with patch(
            "devboard.services.task_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ):
            await task_service.create_task(
                project_id=1,
                title="My Feature Task",
                base_branch="main",
                codebase_id=10,
            )

        call_kwargs = mock_task_repo.create.call_args.kwargs
        assert call_kwargs["branch_name"] == "my-feature-task"

    @pytest.mark.asyncio
    async def test_create_task_uses_provided_branch_name(self, task_service, mock_task_repo):
        """Uses explicitly provided branch name without modification."""
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task_repo.create.return_value = mock_task
        task_service.custom_field_repo.get_mandatory_fields.return_value = []

        with patch(
            "devboard.services.task_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ):
            await task_service.create_task(
                project_id=1,
                title="My Task",
                base_branch="main",
                codebase_id=10,
                branch_name="custom-branch",
            )

        call_kwargs = mock_task_repo.create.call_args.kwargs
        assert call_kwargs["branch_name"] == "custom-branch"

    @pytest.mark.asyncio
    async def test_create_task_passes_model_id_override_to_conversation_service(
        self, task_service, mock_task_repo, mock_conversation_service
    ):
        """Passes model_id_override through to conversation service."""
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task_repo.create.return_value = mock_task
        task_service.custom_field_repo.get_mandatory_fields.return_value = []

        with patch(
            "devboard.services.task_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ):
            await task_service.create_task(
                project_id=1,
                title="My Task",
                base_branch="main",
                codebase_id=10,
                model_id_override="anthropic:claude-opus-4",
            )

        mock_conversation_service.create_initial_conversation_for_parent_entity.assert_called_once_with(
            parent_entity_type=ParentEntityType.TASK,
            parent_entity_id=mock_task.id,
            agent_role=AgentRoleType.TASK_PLANNING,
            model_id_override="anthropic:claude-opus-4",
        )

    @pytest.mark.asyncio
    async def test_create_task_raises_on_missing_mandatory_fields(self, task_service):
        """Raises ValueError when mandatory custom fields are missing."""
        mandatory_field = MagicMock()
        mandatory_field.name = "priority"
        task_service.custom_field_repo.get_mandatory_fields.return_value = [mandatory_field]

        with pytest.raises(ValueError, match="Missing required custom fields: priority"):
            await task_service.create_task(
                project_id=1,
                title="Task",
                base_branch="main",
                codebase_id=10,
            )

    @pytest.mark.asyncio
    async def test_create_task_passes_with_mandatory_fields_provided(self, task_service, mock_task_repo):
        """Succeeds when all mandatory custom fields are provided."""
        mandatory_field = MagicMock()
        mandatory_field.name = "priority"
        task_service.custom_field_repo.get_mandatory_fields.return_value = [mandatory_field]

        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task_repo.create.return_value = mock_task

        with patch(
            "devboard.services.task_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ):
            result = await task_service.create_task(
                project_id=1,
                title="Task",
                base_branch="main",
                codebase_id=10,
                custom_fields={"priority": "high"},
            )

        assert result is mock_task


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


class TestTransitionToMerged:
    """Tests for TaskService.transition_to_merged()."""

    @pytest.fixture
    def task_implementing(self):
        task = MagicMock(spec=Task)
        task.id = 20
        task.status = TaskStatus.IMPLEMENTING
        task.change_summary = None
        task.change_summary_id = None
        task.verify_status_transition.return_value = None
        return task

    def test_returns_new_conversation_id(
        self, task_service, task_implementing, mock_document_repo, mock_conversation_service
    ):
        """transition_to_merged returns the ID of the newly created TASK_FINALISATION conversation."""
        new_conv = MagicMock()
        new_conv.id = 42
        mock_conversation_service.replace_active_conversation.return_value = new_conv

        result = task_service.transition_to_merged(task_implementing, "Summary")

        assert result == 42

    def test_transitions_task_status_to_merged(
        self, task_service, task_implementing, mock_document_repo, mock_conversation_service
    ):
        """transition_to_merged sets task status to MERGED."""
        new_conv = MagicMock()
        new_conv.id = 99
        mock_conversation_service.replace_active_conversation.return_value = new_conv

        task_service.transition_to_merged(task_implementing, "Summary")

        assert task_implementing.status == TaskStatus.MERGED


class TestMergeTaskBranch:
    """Tests for TaskService.merge_task_branch()."""

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

        with patch(
            "devboard.services.task_service.TaskGitService.merge_task_feature_branch",
            new_callable=AsyncMock,
            return_value=mock_merge_result,
        ):
            merge_result, new_conv_id = await task_service.merge_task_branch(task_with_branch, "Changes summary")

        assert merge_result.outcome == MergeOutcome.SUCCESS
        assert isinstance(new_conv_id, int)
        assert task_with_branch.status == TaskStatus.MERGED
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

        with patch(
            "devboard.services.task_service.TaskGitService.merge_task_feature_branch",
            new_callable=AsyncMock,
            return_value=mock_merge_result,
        ):
            merge_result, new_conv_id = await task_service.merge_task_branch(task_with_branch, "Changes summary")

        assert merge_result.outcome == MergeOutcome.SKIPPED
        assert isinstance(new_conv_id, int)
        assert task_with_branch.status == TaskStatus.MERGED
        mock_document_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_fails_with_merge_conflict(self, task_service, task_with_branch, mock_document_repo):
        """Test complete raises MergeFailureError with CONFLICT outcome."""
        mock_merge_result = MergeResult(
            outcome=MergeOutcome.CONFLICT,
            merge_method=MergeMethod.SQUASH,
            message="Conflicts detected between feature and main",
        )

        with patch(
            "devboard.services.task_service.TaskGitService.merge_task_feature_branch",
            new_callable=AsyncMock,
            return_value=mock_merge_result,
        ):
            with pytest.raises(MergeFailureError) as exc_info:
                await task_service.merge_task_branch(task_with_branch, "Changes summary")

        assert exc_info.value.outcome == MergeOutcome.CONFLICT
        assert "Conflicts detected between feature and main" in exc_info.value.message
        mock_document_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_fails_with_merge_error(self, task_service, task_with_branch, mock_document_repo):
        """Test complete raises MergeFailureError with ERROR outcome."""
        mock_merge_result = MergeResult(
            outcome=MergeOutcome.ERROR,
            merge_method=MergeMethod.SQUASH,
            message="Git command failed",
        )

        with patch(
            "devboard.services.task_service.TaskGitService.merge_task_feature_branch",
            new_callable=AsyncMock,
            return_value=mock_merge_result,
        ):
            with pytest.raises(MergeFailureError) as exc_info:
                await task_service.merge_task_branch(task_with_branch, "Changes summary")

        assert exc_info.value.outcome == MergeOutcome.ERROR
        mock_document_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_fails_without_branch_configured(self, task_service, task_with_branch):
        """Test merge raises TaskConfigurationError when task has no branch."""
        task_with_branch.branch_name = None

        with pytest.raises(TaskConfigurationError, match="has no branch configured"):
            await task_service.merge_task_branch(task_with_branch, "Changes summary")


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


class TestEventEmission:
    """Tests verifying SystemEventEmitter is called at the right lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_create_task_emits_task_created(self, task_service, mock_task_repo, mock_system_event_emitter):
        """create_task calls emit_task_created with the created task."""
        mock_task = MagicMock(spec=Task)
        mock_task.id = 1
        mock_task_repo.create.return_value = mock_task
        task_service.custom_field_repo.get_mandatory_fields.return_value = []

        with patch(
            "devboard.services.task_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ):
            result = await task_service.create_task(
                project_id=1,
                title="My Task",
                base_branch="main",
                codebase_id=10,
            )

        mock_system_event_emitter.emit_task_created.assert_called_once_with(result)

    def test_transition_to_complete_emits_with_default_manual_method(self, task_service, mock_system_event_emitter):
        """transition_to_complete emits task.completed with method='manual' by default."""
        task = MagicMock(spec=Task)
        task.verify_status_transition.return_value = None

        task_service.transition_to_complete(task)

        mock_system_event_emitter.emit_task_completed.assert_called_once_with(task, method="manual")

    def test_transition_to_complete_passes_through_method(self, task_service, mock_system_event_emitter):
        """transition_to_complete passes the method arg to emit_task_completed."""
        task = MagicMock(spec=Task)
        task.verify_status_transition.return_value = None

        task_service.transition_to_complete(task, method="archive")

        mock_system_event_emitter.emit_task_completed.assert_called_once_with(task, method="archive")

    @pytest.mark.asyncio
    async def test_merge_task_branch_emits_local_merge(self, task_service, mock_system_event_emitter):
        """merge_task_branch emits task.merged with method='local_merge'."""
        task = MagicMock(spec=Task)
        task.id = 10
        task.branch_name = "feature/test"
        task.change_summary = None
        task.verify_status_transition.return_value = None

        mock_merge_result = MergeResult(
            outcome=MergeOutcome.SUCCESS,
            merge_method=MergeMethod.SQUASH,
            message="Merged",
            merge_commit="abc123",
        )

        with patch(
            "devboard.services.task_service.TaskGitService.merge_task_feature_branch",
            new_callable=AsyncMock,
            return_value=mock_merge_result,
        ):
            await task_service.merge_task_branch(task, "Summary")

        mock_system_event_emitter.emit_task_merged.assert_called_once_with(task, method="local_merge")

    @pytest.mark.asyncio
    async def test_merge_pr_task_emits_pr_merge(self, task_service, mock_system_event_emitter):
        """merge_pr_task emits task.merged with method='pr_merge'."""
        task = MagicMock(spec=Task)
        task.id = 11
        task.github_pr_number = 42
        task.branch_name = "feature/pr-branch"
        task.change_summary = None
        task.codebase = MagicMock()
        task.codebase.local_path = "/repo"
        task.verify_status_transition.return_value = None

        with patch("devboard.services.task_service.GitRepoIntegration") as mock_git_cls:
            mock_git = mock_git_cls.return_value
            mock_git.delete_branch = AsyncMock()
            await task_service.merge_pr_task(task, "PR summary")

        mock_system_event_emitter.emit_task_merged.assert_called_once_with(task, method="pr_merge")

    @pytest.mark.asyncio
    async def test_delete_task_emits_task_deleted_before_deletion(
        self, task_service, mock_task_repo, mock_system_event_emitter
    ):
        """delete_task emits task.deleted before the hard delete."""
        task = MagicMock(spec=Task)
        task.id = 20
        task.specification_id = None
        task.implementation_plan_id = None

        call_order = []
        mock_system_event_emitter.emit_task_deleted.side_effect = lambda t: call_order.append("emit")
        mock_task_repo.delete.side_effect = lambda t: call_order.append("delete")

        await task_service.delete_task(task)

        mock_system_event_emitter.emit_task_deleted.assert_called_once_with(task)
        assert call_order.index("emit") < call_order.index("delete")


class TestIsTaskAgentRunning:
    """Tests for TaskService.is_task_agent_running()."""

    def test_returns_false_when_no_active_conversation(self, task_service):
        """Returns False when no active conversation exists for the task."""
        from devboard.db.repositories.conversation import NoActiveConversationError

        task_service.conversation_service.conversation_repo.get_active_conversation_for_entity.side_effect = (
            NoActiveConversationError("no conversation")
        )

        result = task_service.is_task_agent_running(task_id=42)

        assert result is False

    def test_returns_false_when_conversation_exists_but_not_running(self, task_service):
        """Returns False when active conversation exists but no running execution."""
        mock_conv = MagicMock()
        mock_conv.id = 100
        task_service.conversation_service.conversation_repo.get_active_conversation_for_entity.return_value = mock_conv

        with patch("devboard.services.task_service.get_execution_manager") as mock_get_mgr:
            mock_mgr = MagicMock()
            mock_mgr.has_active_execution.return_value = False
            mock_get_mgr.return_value = mock_mgr

            result = task_service.is_task_agent_running(task_id=42)

        assert result is False
        mock_mgr.has_active_execution.assert_called_once_with(100)

    def test_returns_true_when_conversation_has_running_execution(self, task_service):
        """Returns True when active conversation has a running execution."""
        mock_conv = MagicMock()
        mock_conv.id = 100
        task_service.conversation_service.conversation_repo.get_active_conversation_for_entity.return_value = mock_conv

        with patch("devboard.services.task_service.get_execution_manager") as mock_get_mgr:
            mock_mgr = MagicMock()
            mock_mgr.has_active_execution.return_value = True
            mock_get_mgr.return_value = mock_mgr

            result = task_service.is_task_agent_running(task_id=42)

        assert result is True
        mock_mgr.has_active_execution.assert_called_once_with(100)
