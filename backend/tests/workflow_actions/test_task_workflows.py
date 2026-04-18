from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.tools.rebase_tools import RebaseActionResult
from devboard.db.models.codebase import MergeMethod
from devboard.db.models.implementation_plan import ImplementationPlan, ImplementationStep, ImplementationStepType
from devboard.db.models.task import TaskStatus
from devboard.integrations.types import BranchComparison, FileDiff, GitLogEntry, StructuredDiff
from devboard.services.workspace.types import AllocationResult
from devboard.workflow_actions.task_workflows import (
    ApproveAndCreatePRAction,
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


def _make_approve_and_merge_action(task, workspace_service=None) -> ApproveAndMergeAction:
    return ApproveAndMergeAction(
        task=task,
        task_service=Mock(),
        conversation_repo=Mock(),
        agent_config_service=Mock(),
        document_repository=Mock(),
        integration_service=Mock(),
        workspace_service=workspace_service or Mock(),
    )


def _make_approve_and_create_pr_action(
    task,
    workspace_service=None,
    integration_service=None,
) -> ApproveAndCreatePRAction:
    return ApproveAndCreatePRAction(
        task=task,
        task_service=Mock(),
        conversation_repo=Mock(),
        agent_config_service=Mock(),
        document_repository=Mock(),
        integration_service=integration_service or Mock(),
        workspace_service=workspace_service or Mock(),
    )


def _make_github_integration_service(connection_success: bool = True, connection_message: str = "OK") -> Mock:
    """Build a mock IntegrationService pre-configured with a GitHub integration stub."""
    github_mock = Mock()
    github_mock.test_connection = AsyncMock(return_value=Mock(success=connection_success, message=connection_message))
    integration_service = Mock()
    integration_service.get_integration_instance.return_value = github_mock
    return integration_service


@pytest.fixture
def mock_workspace_service_for_merge():
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


_NO_CONFLICTS_COMPARISON = BranchComparison(ahead=2, behind=0, has_conflicts=False, can_merge=True)
_CONFLICTS_COMPARISON = BranchComparison(ahead=2, behind=1, has_conflicts=True, can_merge=False)


class TestApproveAndMergeActionRun:
    @pytest.fixture
    def mock_task(self):
        task = Mock()
        task.id = 1
        task.branch_name = "feature/test"
        task.base_branch = "main"
        task.codebase.merge_method = MergeMethod.SQUASH
        task.codebase.local_path = "/repo"
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
    async def test_returns_prompt_when_no_overlap_and_no_conflicts(self, mock_task):
        """run() returns a merge prompt when there are no uncommitted conflicts and branch is not behind."""
        action = _make_approve_and_merge_action(mock_task)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_base_conflicting_uncommitted_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_NO_CONFLICTS_COMPARISON,
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
        assert "rebased" not in result  # no rebase note

    @pytest.mark.asyncio
    async def test_auto_rebases_and_proceeds_on_clean_rebase(self, mock_task, mock_workspace_service_for_merge):
        """When branch has conflicts, auto-rebases and returns merge prompt with a rebase note."""
        action = _make_approve_and_merge_action(mock_task, workspace_service=mock_workspace_service_for_merge)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_base_conflicting_uncommitted_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_CONFLICTS_COMPARISON,
            ),
            patch(
                "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
                new_callable=AsyncMock,
                return_value=RebaseActionResult(success=True, message="Rebase done.", has_base_changes=False),
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
        assert "rebased" in result  # rebase note prepended

    @pytest.mark.asyncio
    async def test_returns_combined_conflict_and_merge_prompt(self, mock_task, mock_workspace_service_for_merge):
        """When rebase has conflicts, returns conflict resolution prompt combined with merge instructions."""
        action = _make_approve_and_merge_action(mock_task, workspace_service=mock_workspace_service_for_merge)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_base_conflicting_uncommitted_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_CONFLICTS_COMPARISON,
            ),
            patch(
                "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
                new_callable=AsyncMock,
                return_value=RebaseActionResult(
                    success=False, message="Conflicts in src/api.py", rebase_complete=False
                ),
            ),
        ):
            result = await action.run()

        assert result is not None
        assert "Conflicts in src/api.py" in result
        assert "complete_task_with_local_merge" in result

    @pytest.mark.asyncio
    async def test_stash_conflict_returns_stash_conflict_prompt_with_merge_instructions(
        self, mock_task, mock_workspace_service_for_merge
    ):
        """When auto-rebase results in STASH_CONFLICT, returns stash-focused prompt (not 'rebase in progress')."""
        action = _make_approve_and_merge_action(mock_task, workspace_service=mock_workspace_service_for_merge)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.TaskGitService.get_base_conflicting_uncommitted_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_CONFLICTS_COMPARISON,
            ),
            patch(
                "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
                new_callable=AsyncMock,
                return_value=RebaseActionResult(
                    success=False,
                    message="Rebase completed but stash restore conflicted in src/api.py",
                    rebase_complete=True,
                ),
            ),
        ):
            result = await action.run()

        assert result is not None
        assert "stash" in result.lower()
        assert "complete_task_with_local_merge" in result
        assert "rebase is complete" not in result  # must not say rebase is still in progress


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
    async def test_allocates_workspace_for_planning(self, mock_task, mock_workspace_service):
        """PLANNING state: workspace is allocated and prepared before calling rebase."""
        action = self._make_action(mock_task, mock_workspace_service)

        rebase_result = RebaseActionResult(success=True, message="Rebase completed successfully.")
        with patch(
            "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
            new_callable=AsyncMock,
            return_value=rebase_result,
        ):
            result = await action.run()

        assert result is None  # no base branch changes

    @pytest.mark.asyncio
    async def test_allocates_workspace_for_implementing(self, mock_task, mock_workspace_service):
        """IMPLEMENTING state: workspace is also allocated and prepared (unified flow)."""
        mock_task.status = TaskStatus.IMPLEMENTING
        action = self._make_action(mock_task, mock_workspace_service)

        rebase_result = RebaseActionResult(success=True, message="Rebase completed successfully.")
        with patch(
            "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
            new_callable=AsyncMock,
            return_value=rebase_result,
        ):
            result = await action.run()

        assert result is None  # no base branch changes

    @pytest.mark.parametrize("status", [TaskStatus.PLANNING, TaskStatus.IMPLEMENTING])
    @pytest.mark.asyncio
    async def test_returns_conflict_prompt_on_conflict(self, mock_task, mock_workspace_service, status):
        """Conflict result returns the conflict message as the agent prompt (not raises)."""
        mock_task.status = status
        action = self._make_action(mock_task, mock_workspace_service)

        rebase_result = RebaseActionResult(success=False, message="Conflicts in src/api.py and src/models.py")
        with patch(
            "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
            new_callable=AsyncMock,
            return_value=rebase_result,
        ):
            result = await action.run()

        assert result == "Conflicts in src/api.py and src/models.py"

    @pytest.mark.asyncio
    async def test_returns_base_changes_prompt_on_success_with_changes(self, mock_task, mock_workspace_service):
        """Success with base branch changes returns the review prompt."""
        action = self._make_action(mock_task, mock_workspace_service)

        rebase_result = RebaseActionResult(
            success=True, message="Rebase done.\n\n3 commits changed 5 files\n\nPlease review.", has_base_changes=True
        )
        with patch(
            "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
            new_callable=AsyncMock,
            return_value=rebase_result,
        ):
            result = await action.run()

        assert result == rebase_result.message

    @pytest.mark.asyncio
    async def test_returns_none_on_success_without_base_changes(self, mock_task, mock_workspace_service):
        """Success with no base branch changes returns None (no agent prompt needed)."""
        action = self._make_action(mock_task, mock_workspace_service)

        rebase_result = RebaseActionResult(
            success=True, message="Rebase completed successfully.", has_base_changes=False
        )
        with patch(
            "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
            new_callable=AsyncMock,
            return_value=rebase_result,
        ):
            result = await action.run()

        assert result is None


class TestApproveAndCreatePRActionRun:
    @pytest.fixture
    def mock_task(self):
        task = Mock()
        task.id = 1
        task.branch_name = "feature/test"
        task.base_branch = "main"
        task.codebase.merge_method = MergeMethod.SQUASH
        task.codebase.local_path = "/repo"
        task.last_used_worktree_slot = None
        return task

    def _make_action(self, task, workspace_service=None) -> ApproveAndCreatePRAction:
        return _make_approve_and_create_pr_action(
            task,
            workspace_service=workspace_service,
            integration_service=_make_github_integration_service(),
        )

    @pytest.mark.asyncio
    async def test_raises_github_error_on_failed_connection(self, mock_task):
        """run() raises GitHubConnectionError when GitHub connection fails."""
        from devboard.services.task_git.types import GitHubConnectionError

        action = _make_approve_and_create_pr_action(
            mock_task,
            integration_service=_make_github_integration_service(
                connection_success=False, connection_message="token invalid"
            ),
        )

        with pytest.raises(GitHubConnectionError, match="token invalid"):
            await action.run()

    @pytest.mark.asyncio
    async def test_returns_pr_prompt_when_no_conflicts(self, mock_task):
        """run() returns a PR creation prompt when branch is up to date."""
        action = self._make_action(mock_task)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_NO_CONFLICTS_COMPARISON,
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
        assert "create_pull_request" in result
        assert "rebased" not in result

    @pytest.mark.asyncio
    async def test_auto_rebases_and_proceeds_on_clean_rebase(self, mock_task, mock_workspace_service_for_merge):
        """When branch is behind, auto-rebases and returns PR prompt with a rebase note."""
        action = self._make_action(mock_task, workspace_service=mock_workspace_service_for_merge)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_CONFLICTS_COMPARISON,
            ),
            patch(
                "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
                new_callable=AsyncMock,
                return_value=RebaseActionResult(success=True, message="Rebase done.", has_base_changes=False),
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
        assert "create_pull_request" in result
        assert "rebased" in result

    @pytest.mark.asyncio
    async def test_returns_combined_conflict_and_pr_prompt(self, mock_task, mock_workspace_service_for_merge):
        """When rebase has conflicts, returns conflict resolution prompt combined with PR instructions."""
        action = self._make_action(mock_task, workspace_service=mock_workspace_service_for_merge)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_CONFLICTS_COMPARISON,
            ),
            patch(
                "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
                new_callable=AsyncMock,
                return_value=RebaseActionResult(
                    success=False, message="Conflicts in src/models.py", rebase_complete=False
                ),
            ),
        ):
            result = await action.run()

        assert result is not None
        assert "Conflicts in src/models.py" in result
        assert "create_pull_request" in result

    @pytest.mark.asyncio
    async def test_stash_conflict_returns_stash_conflict_prompt_with_pr_instructions(
        self, mock_task, mock_workspace_service_for_merge
    ):
        """When auto-rebase results in STASH_CONFLICT, returns stash-focused prompt (not 'rebase in progress')."""
        action = self._make_action(mock_task, workspace_service=mock_workspace_service_for_merge)

        with (
            patch(
                "devboard.workflow_actions.task_workflows.GitRepoIntegration.get_branch_comparison",
                new_callable=AsyncMock,
                return_value=_CONFLICTS_COMPARISON,
            ),
            patch(
                "devboard.workflow_actions.task_workflows.execute_rebase_with_result",
                new_callable=AsyncMock,
                return_value=RebaseActionResult(
                    success=False,
                    message="Rebase completed but stash restore conflicted in src/models.py",
                    rebase_complete=True,
                ),
            ),
        ):
            result = await action.run()

        assert result is not None
        assert "stash" in result.lower()
        assert "create_pull_request" in result
        assert "rebase is complete" not in result  # must not say rebase is still in progress
