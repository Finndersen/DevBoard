from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.db.models.codebase import MergeMethod
from devboard.db.models.implementation_plan import ImplementationPlan, ImplementationStep, ImplementationStepType
from devboard.db.models.task import TaskStatus
from devboard.integrations.types import FileDiff, GitLogEntry, StructuredDiff
from devboard.services.task_git.types import BaseBranchChanges, RebaseOutcome, RebaseResult
from devboard.services.workspace.types import AllocationResult
from devboard.workflow_actions.task_workflows import (
    ApproveAndMergeAction,
    BeginImplementationAction,
    RebaseTaskBranchAction,
    _get_task_changes_prompt_context,
)


@pytest.fixture
def mock_task():
    task = Mock()
    task.id = 1
    task.branch_name = "feature/test"
    task.base_branch = "main"
    return task


class TestGetTaskChangesPromptContext:
    @pytest.mark.asyncio
    async def test_no_worktree_slot_returns_fallback(self, mock_task):
        mock_task.last_used_worktree_slot = None

        result = await _get_task_changes_prompt_context(mock_task)

        assert "Unable to determine branch state" in result
        assert "no worktree slot found" in result

    @pytest.mark.asyncio
    async def test_worktree_with_uncommitted_changes(self, mock_task):
        mock_task.last_used_worktree_slot = Mock(path="/tmp/slot")

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_commit_metadata",
                new_callable=AsyncMock,
                return_value=[
                    GitLogEntry(hash="abc1234", author="Test", date="2024-01-01", subject="First commit"),
                    GitLogEntry(hash="def5678", author="Test", date="2024-01-02", subject="Second commit"),
                ],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_uncommitted_changes",
                new_callable=AsyncMock,
                return_value=StructuredDiff(
                    files=[
                        FileDiff(file_path="src/new.py", diff_content="", additions=10, deletions=0, is_new_file=True),
                    ],
                    additions=10,
                    deletions=0,
                ),
            ),
        ):
            result = await _get_task_changes_prompt_context(mock_task)

        assert "Commits on task branch" in result
        assert "abc1234: First commit" in result
        assert "def5678: Second commit" in result
        assert "Uncommitted changes" in result
        assert "src/new.py (+10/-0) (new)" in result

    @pytest.mark.asyncio
    async def test_worktree_with_no_uncommitted_changes(self, mock_task):
        mock_task.last_used_worktree_slot = Mock(path="/tmp/slot")

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_commit_metadata",
                new_callable=AsyncMock,
                return_value=[
                    GitLogEntry(hash="abc1234", author="Test", date="2024-01-01", subject="Implement feature"),
                ],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_uncommitted_changes",
                new_callable=AsyncMock,
                return_value=StructuredDiff(files=[], additions=0, deletions=0),
            ),
        ):
            result = await _get_task_changes_prompt_context(mock_task)

        assert "Commits on task branch" in result
        assert "abc1234: Implement feature" in result
        assert "No uncommitted changes" in result
        assert "Uncommitted changes:" not in result

    @pytest.mark.asyncio
    async def test_worktree_with_no_commits(self, mock_task):
        mock_task.last_used_worktree_slot = Mock(path="/tmp/slot")

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_commit_metadata",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_uncommitted_changes",
                new_callable=AsyncMock,
                return_value=StructuredDiff(
                    files=[
                        FileDiff(file_path="src/foo.py", diff_content="", additions=5, deletions=2),
                    ],
                    additions=5,
                    deletions=2,
                ),
            ),
        ):
            result = await _get_task_changes_prompt_context(mock_task)

        assert "No commits on task branch yet" in result
        assert "Uncommitted changes" in result
        assert "src/foo.py (+5/-2)" in result


class TestApproveAndMergePrompt:
    CHANGES_CONTEXT = "```\nNo commits on task branch yet.\n\nUncommitted changes:\n  src/foo.py (+5/-2)\n```"

    @pytest.mark.parametrize(
        "merge_method,expected_phrases",
        [
            (MergeMethod.SQUASH, ["single commit", "squashed"]),
            (MergeMethod.REBASE, ["atomic commits", "replayed"]),
            (MergeMethod.MERGE_COMMIT, ["appropriate commit(s)", "preserved"]),
        ],
    )
    def test_commit_instruction_by_merge_method(self, merge_method: MergeMethod, expected_phrases: list[str]):
        prompt = ApproveAndMergeAction._build_prompt(merge_method, self.CHANGES_CONTEXT)

        for phrase in expected_phrases:
            assert phrase in prompt

    @pytest.mark.parametrize("merge_method", list(MergeMethod))
    def test_always_includes_complete_task_tool(self, merge_method: MergeMethod):
        prompt = ApproveAndMergeAction._build_prompt(merge_method, self.CHANGES_CONTEXT)

        assert "complete_task_with_local_merge" in prompt

    def test_unknown_merge_method_uses_fallback(self):
        prompt = ApproveAndMergeAction._build_prompt("unknown_method", self.CHANGES_CONTEXT)

        assert "appropriate commit(s)" in prompt
        assert "clear commit messages" in prompt
        assert "complete_task_with_local_merge" in prompt


def _make_action(action_class, task, **kwargs):
    return action_class(
        task=task,
        task_service=Mock(),
        conversation_repo=Mock(),
        agent_config_service=Mock(),
        document_repository=Mock(),
        integration_service=Mock(),
        workspace_service=Mock(),
        **kwargs,
    )


def _make_approve_and_merge_action(task) -> ApproveAndMergeAction:
    return _make_action(ApproveAndMergeAction, task)


class TestApproveAndMergeActionRun:
    @pytest.fixture
    def mock_task(self):
        task = Mock()
        task.id = 1
        task.branch_name = "feature/test"
        task.base_branch = "main"
        task.codebase.merge_method = MergeMethod.SQUASH
        task.last_used_worktree_slot = None
        return task

    @pytest.mark.asyncio
    async def test_raises_value_error_when_overlap_detected(self, mock_task):
        """run() raises ValueError listing conflicting files when base has overlapping uncommitted changes."""
        action = _make_approve_and_merge_action(mock_task)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_base_conflicting_uncommitted_files",
                new_callable=AsyncMock,
                return_value=["src/api.py", "src/models.py"],
            ),
            pytest.raises(ValueError) as exc_info,
        ):
            await action.run()

        error_msg = str(exc_info.value)
        assert "src/api.py" in error_msg
        assert "src/models.py" in error_msg
        assert "commit or stash" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_returns_prompt_when_no_overlap(self, mock_task):
        """run() returns a prompt string when there are no conflicting uncommitted changes."""
        action = _make_approve_and_merge_action(mock_task)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_base_conflicting_uncommitted_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_commit_metadata",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_task_uncommitted_changes",
                new_callable=AsyncMock,
                return_value=Mock(files=[], format_summary=Mock(return_value="")),
            ),
        ):
            result = await action.run()

        assert result is not None
        assert "complete_task_with_local_merge" in result


def _make_begin_implementation_action(task) -> BeginImplementationAction:
    return _make_action(BeginImplementationAction, task)


class TestBeginImplementationActionRun:
    @pytest.fixture
    def mock_task_with_plan(self):
        step1 = Mock(spec=ImplementationStep)
        step1.step_number = 1
        step1.title = "Set up database schema"
        step1.type = ImplementationStepType.CODE_CHANGE
        step1.dependencies = []
        step1.status = "pending"
        step1.outcome = None

        step2 = Mock(spec=ImplementationStep)
        step2.step_number = 2
        step2.title = "Implement API endpoints"
        step2.type = ImplementationStepType.CODE_CHANGE
        step2.dependencies = [1]
        step2.status = "pending"
        step2.outcome = None

        plan = Mock(spec=ImplementationPlan)
        plan.steps = [step1, step2]

        task = Mock()
        task.id = 1
        task.implementation_plan_structured = plan
        return task

    @pytest.mark.asyncio
    async def test_returns_prompt_with_execution_graph(self, mock_task_with_plan):
        """run() returns a prompt that includes the execution graph appended below."""
        action = _make_begin_implementation_action(mock_task_with_plan)

        result = await action.run()

        assert result is not None
        assert "execution graph below" in result
        assert "EXECUTION GRAPH:" in result
        assert "Layer 1" in result
        assert "Layer 2" in result
        assert "Set up database schema" in result
        assert "Implement API endpoints" in result

    @pytest.mark.asyncio
    async def test_returns_base_prompt_without_graph_when_no_plan(self):
        """run() returns only the base prompt when task has no structured plan."""
        task = Mock()
        task.id = 1
        task.implementation_plan_structured = None
        action = _make_begin_implementation_action(task)

        result = await action.run()

        assert result is not None
        assert "EXECUTION GRAPH:" not in result
        assert "The implementation plan has been approved" in result


class TestRebaseTaskBranchAction:
    @pytest.fixture
    def mock_task(self):
        task = Mock()
        task.id = 1
        task.branch_name = "feature/test"
        task.base_branch = "main"
        task.status = TaskStatus.PLANNING
        task.last_used_worktree_slot = None
        return task

    @pytest.fixture
    def mock_workspace_service(self):
        """WorkspaceService stub that yields a mock AllocationResult."""
        service = Mock()
        slot = Mock()
        slot.path = "/worktrees/slot-1"
        allocation = AllocationResult(slot=slot, reused=False)

        @asynccontextmanager
        async def _allocate_workspace(task):
            yield allocation

        async def _prepare_workspace(task, slot):
            return
            yield  # make it an async generator

        service.allocate_workspace = _allocate_workspace
        service.prepare_workspace = _prepare_workspace
        return service

    def _make_action(self, task, workspace_service) -> RebaseTaskBranchAction:
        return RebaseTaskBranchAction(
            task=task,
            task_service=Mock(),
            conversation_repo=Mock(),
            agent_config_service=Mock(),
            document_repository=Mock(),
            integration_service=Mock(),
            workspace_service=workspace_service,
        )

    @pytest.mark.asyncio
    async def test_planning_allocates_workspace_before_rebase(self, mock_task, mock_workspace_service):
        """PLANNING state: workspace is allocated and prepared before calling rebase."""
        action = self._make_action(mock_task, mock_workspace_service)

        rebase_result = RebaseResult(outcome=RebaseOutcome.SUCCESS, slot_path="/worktrees/slot-1")
        with patch(
            "devboard.workflow_actions.task_workflows.TaskGitService.rebase_task_branch",
            new_callable=AsyncMock,
            return_value=rebase_result,
        ):
            result = await action.run()

        assert result is None  # no base branch changes

    @pytest.mark.asyncio
    async def test_planning_raises_on_conflict(self, mock_task, mock_workspace_service):
        """PLANNING state: conflict result raises ValueError."""
        action = self._make_action(mock_task, mock_workspace_service)

        rebase_result = RebaseResult(
            outcome=RebaseOutcome.CONFLICT,
            slot_path="/worktrees/slot-1",
            conflicted_files=["src/api.py", "src/models.py"],
        )
        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.rebase_task_branch",
                new_callable=AsyncMock,
                return_value=rebase_result,
            ),
            pytest.raises(ValueError, match="conflicts"),
        ):
            await action.run()

    @pytest.mark.asyncio
    async def test_planning_returns_base_changes_prompt(self, mock_task, mock_workspace_service):
        """PLANNING state: when base branch changed, returns a prompt summarising the changes."""
        action = self._make_action(mock_task, mock_workspace_service)

        base_changes = Mock(spec=BaseBranchChanges)
        base_changes.format_summary.return_value = "3 commits changed 5 files"
        rebase_result = RebaseResult(
            outcome=RebaseOutcome.SUCCESS,
            slot_path="/worktrees/slot-1",
            base_branch_changes=base_changes,
        )
        with patch(
            "devboard.workflow_actions.task_workflows.TaskGitService.rebase_task_branch",
            new_callable=AsyncMock,
            return_value=rebase_result,
        ):
            result = await action.run()

        assert result is not None
        assert "3 commits changed 5 files" in result

    @pytest.mark.asyncio
    async def test_implementing_returns_prompt_without_workspace_allocation(self, mock_task, mock_workspace_service):
        """IMPLEMENTING state: returns agent prompt directly, never calls allocate_workspace."""
        mock_task.status = TaskStatus.IMPLEMENTING
        action = self._make_action(mock_task, mock_workspace_service)

        # Spy on the context manager — if called, the test should fail
        original = mock_workspace_service.allocate_workspace
        called = []

        @asynccontextmanager
        async def spy(task):
            called.append(task)
            async with original(task) as alloc:
                yield alloc

        mock_workspace_service.allocate_workspace = spy

        result = await action.run()

        assert called == [], "allocate_workspace should not be called in IMPLEMENTING state"
        assert result is not None
        assert "rebase_task_branch" in result
