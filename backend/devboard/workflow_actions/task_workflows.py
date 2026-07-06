from devboard.agents.system_message_tags import wrap_system_message
from devboard.agents.tools.rebase_tools import RebaseActionResult, execute_rebase_with_result
from devboard.db.models import ParentEntityType, Task
from devboard.db.models.codebase import BranchHandling, MergeMethod
from devboard.db.models.conversation import AgentRoleType
from devboard.db.models.task import TaskStatus
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_git.types import GitHubConnectionError
from devboard.services.task_git_service import TaskGitService
from devboard.workflow_actions.base import TaskWorkflowAction

_CHANGE_SUMMARY_PROMPT_GUIDANCE = (
    "Include a change_summary grouping changes by type "
    "(Functional / Bug Fix / Optimisation / Refactor / Cosmetic — omit empty categories). "
    "If anything deviates from the agreed spec, include a Deviations from Specification section. "
    "Optionally include a Learnings section for non-obvious discoveries useful for follow-up tasks or documentation."
)


async def _get_task_changes_prompt_context(task: Task) -> str:
    """Build a prompt context string describing the current state of changes on the task branch.

    Returns a string with commit history and uncommitted change details that can be
    inserted into finalisation action prompts.
    """
    # Check if a worktree slot exists
    last_used_slot = task.last_used_worktree_slot

    if not last_used_slot:
        return "Unable to determine branch state — no worktree slot found for this task."

    # Fetch commit history and uncommitted changes
    commits = await TaskGitService.get_task_commit_metadata(task)
    uncommitted = await TaskGitService.get_task_uncommitted_changes(task)

    parts: list[str] = []

    # Commit history
    if commits:
        commit_list = "\n".join(f"  - {c.hash[:7]}: {c.subject}" for c in commits)
        parts.append(f"Commits on task branch ({len(commits)}):\n{commit_list}")
    else:
        parts.append("No commits on task branch yet.")

    # Uncommitted changes
    if uncommitted.files:
        parts.append(f"Uncommitted changes:\n{uncommitted.format_summary()}")
    else:
        parts.append("No uncommitted changes.")

    return "```\n" + "\n\n".join(parts) + "\n```"


def _build_rebase_conflict_prompt(rebase_result: RebaseActionResult, continuation: str, next_instructions: str) -> str:
    """Combine a rebase_result system-message block with its actionable message and follow-up instructions."""
    prompt = wrap_system_message(rebase_result.git_diff_details, "rebase_result")
    if rebase_result.message:
        prompt += "\n\n" + rebase_result.message
    return prompt + f"\n\n{continuation}\n\n" + next_instructions


class CreateImplementationPlanAction(TaskWorkflowAction):
    """Creates an implementation plan document and prompts the agent to generate it.

    Does NOT change task status — task remains in PLANNING throughout.
    The same conversation is used for both specification and planning work.
    """

    KEY = "task.create_implementation_plan"

    PROMPT = "The user has approved the task specification. Create the implementation plan now."

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return (
            task.status == TaskStatus.PLANNING
            and bool(task.specification.content.strip())
            and not task.implementation_plan_structured
            and task.implementation_plan is None
        )

    async def run(self) -> str | None:
        # No pre-creation needed — the planning agent creates the ImplementationPlan
        # via the set_implementation_plan_steps tool directly
        return self.PROMPT


class BeginImplementationAction(TaskWorkflowAction):
    """Transitions a task to IMPLEMENTING and creates a new implementation conversation.

    Always creates a new conversation to provide clean context for implementation.
    """

    KEY = "task.begin_implementation"

    PROMPT_TEMPLATE = "The implementation plan has been approved. Review the plan and begin execution — use `execute_implementation_step` to run each step, consulting the execution graph above to identify steps that can run in parallel."

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return (
            task.status == TaskStatus.PLANNING
            and task.implementation_plan_structured is not None
            and task.implementation_plan_structured.status == "pending"
        )

    async def run(self) -> str | None:
        self.task_service.transition_to_implementing(self.task)
        self.conversation_service.replace_active_conversation(
            entity_type=ParentEntityType.TASK,
            entity_id=self.task.id,
            new_agent_role=AgentRoleType.TASK_IMPLEMENTATION,
        )
        self.conversation_repo.commit()
        return self.PROMPT_TEMPLATE


class RebaseTaskBranchAction(TaskWorkflowAction):
    """Rebases a task's feature branch onto its base branch.

    Always runs the rebase directly (allocating a workspace), regardless of task status.
    On conflict, returns the conflict prompt for the agent to resolve files and continue.
    """

    KEY = "task.rebase_branch"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return task.status in (TaskStatus.PLANNING, TaskStatus.IMPLEMENTING)

    async def run(self) -> str | None:
        async with self.workspace_service.allocate_workspace(self.task) as allocation:
            async for _ in self.workspace_service.prepare_workspace(self.task, allocation.slot):
                pass
            result = await execute_rebase_with_result(self.task)

        # Success with no base branch changes: nothing worth prompting the agent about
        if result.success and not result.has_base_changes:
            return None

        rebase_result = wrap_system_message(result.git_diff_details, "rebase_result")
        return rebase_result + "\n\n" + result.message if result.message else rebase_result


_FINALISATION_INSTRUCTIONS = (
    "## Instructions\n"
    "IMPORTANT: The git status above already contains the current branch state including commits and uncommitted changes. "
    "Do NOT run git status, git log, or git diff commands to inspect the branch — use the information provided above.\n\n"
    'If there are uncommitted changes, create appropriate commit(s) using `git add -A && git commit -m "..."` '
    "with clear commit messages first."
)


class ApproveAndMergeAction(TaskWorkflowAction):
    """Approve changes and merge feature branch locally."""

    KEY = "task.approve_and_merge"

    _COMMIT_INSTRUCTIONS: dict[str, str] = {
        MergeMethod.SQUASH: 'If there are uncommitted changes, commit them with `git add -A && git commit -m "..."` — a single commit is fine since all commits will be squashed into one at merge time.',
        MergeMethod.REBASE: 'If there are uncommitted changes, create logical, atomic commits using `git add -A && git commit -m "..."` — each commit will be individually replayed onto the base branch.',
        MergeMethod.MERGE_COMMIT: 'If there are uncommitted changes, create appropriate commit(s) using `git add -A && git commit -m "..."` — each commit will be preserved in the full merge history.',
    }

    @staticmethod
    def _build_prompt(merge_method: str, changes_context: str) -> str:
        commit_instruction = ApproveAndMergeAction._COMMIT_INSTRUCTIONS.get(
            merge_method,
            "If there are uncommitted changes, create appropriate commit(s) with clear commit messages first.",
        )
        git_status = wrap_system_message(f"## Git Status\n{changes_context}", "git_status")
        instructions = (
            _FINALISATION_INSTRUCTIONS
            + f"\n\n{commit_instruction}"
            + "\n\nOnce all changes are committed, use the `merge_branch_and_finalise` tool to merge the feature branch and transition to finalisation. "
            + _CHANGE_SUMMARY_PROMPT_GUIDANCE
        )
        return git_status + "\n\n" + instructions

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return (
            task.status == TaskStatus.IMPLEMENTING
            and task.codebase.branch_handling == BranchHandling.DIRECT_MERGE.value
        )

    async def run(self) -> str | None:
        overlapping = await TaskGitService.get_base_conflicting_uncommitted_files(self.task)
        if overlapping:
            file_list = "\n".join(f"  - {f}" for f in sorted(overlapping))
            raise ValueError(
                f"Cannot proceed: the main repo has uncommitted changes that conflict with task branch files:\n{file_list}\n"
                "Please commit or stash these changes before merging."
            )

        main_git = GitRepoIntegration(self.task.codebase.local_path)
        comparison = await main_git.get_branch_comparison(self.task.branch_name, self.task.base_branch)
        rebase_note = ""
        if comparison.has_conflicts or comparison.behind > 0:
            async with self.workspace_service.allocate_workspace(self.task) as allocation:
                async for _ in self.workspace_service.prepare_workspace(self.task, allocation.slot):
                    pass
                rebase_result = await execute_rebase_with_result(self.task)

            if not rebase_result.success:
                if rebase_result.rebase_complete:
                    # STASH_CONFLICT: rebase committed but stash restore conflicted — no further rebase needed
                    merge_instructions = self._build_prompt(
                        self.task.codebase.merge_method,
                        "(git status available once stash conflicts are resolved)",
                    )
                    return _build_rebase_conflict_prompt(
                        rebase_result, "Once stash conflicts are resolved:", merge_instructions
                    )
                else:
                    # CONFLICT: rebase still in progress
                    merge_instructions = self._build_prompt(
                        self.task.codebase.merge_method, "(git status will be available once rebase is complete)"
                    )
                    return _build_rebase_conflict_prompt(
                        rebase_result, "Once the rebase is complete:", merge_instructions
                    )

            rebase_note = f"The task branch was rebased onto `{self.task.base_branch}` before merging.\n\n"

        # Note: last_used_worktree_slot is accessed after workspace release but before reallocation;
        # reads are safe within the same request as reallocation requires another task to claim the slot.
        changes_context = await _get_task_changes_prompt_context(self.task)
        prompt = self._build_prompt(self.task.codebase.merge_method, changes_context)
        return rebase_note + prompt if rebase_note else prompt


class ApproveAndCreatePRAction(TaskWorkflowAction):
    """Approve changes and create a GitHub pull request."""

    KEY = "task.approve_and_create_pr"

    # Commit instructions for PR flow: inform about style expectations without directing squash
    # (the feature branch is pushed as-is; GitHub handles squash/rebase/merge at PR merge time)
    _COMMIT_INSTRUCTIONS: dict[str, str] = {
        MergeMethod.SQUASH: 'If there are uncommitted changes, commit them with `git add -A && git commit -m "..."` — a single commit is fine; GitHub will squash all commits at PR merge time.',
        MergeMethod.REBASE: 'If there are uncommitted changes, create logical, atomic commits using `git add -A && git commit -m "..."` — each commit will be individually replayed at PR merge time.',
        MergeMethod.MERGE_COMMIT: 'If there are uncommitted changes, create appropriate commit(s) using `git add -A && git commit -m "..."` — each commit will be preserved in the merge history.',
    }

    _PR_INSTRUCTIONS = """
Once all changes are committed, use the `create_pull_request` tool to create a GitHub PR.

When creating the PR:
- Use a clear, descriptive title that summarizes what this task accomplishes
- Write a comprehensive PR description that includes:
  - Context of the task and its purpose
  - A summary of the changes made
  - Any notable implementation decisions
  - Testing notes if applicable

The PR will be created against the base branch and the task will transition to PR_OPEN status."""

    @staticmethod
    def _build_prompt(merge_method: str, changes_context: str) -> str:
        commit_instruction = ApproveAndCreatePRAction._COMMIT_INSTRUCTIONS.get(
            merge_method,
            'If there are uncommitted changes, create appropriate commit(s) using `git add -A && git commit -m "..."` with clear commit messages first.',
        )
        git_status = wrap_system_message(f"## Git Status\n{changes_context}", "git_status")
        instructions = (
            _FINALISATION_INSTRUCTIONS + f"\n\n{commit_instruction}" + ApproveAndCreatePRAction._PR_INSTRUCTIONS
        )
        return git_status + "\n\n" + instructions

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return (
            task.status == TaskStatus.IMPLEMENTING
            and task.codebase.repository_url is not None
            and task.codebase.branch_handling == BranchHandling.GITHUB_PR.value
        )

    async def run(self) -> str | None:
        github = self.integration_service.get_integration_instance(GitHubIntegration)
        connection_result = await github.test_connection()
        if not connection_result.success:
            raise GitHubConnectionError(f"GitHub connection failed: {connection_result.message}")

        main_git = GitRepoIntegration(self.task.codebase.local_path)
        comparison = await main_git.get_branch_comparison(self.task.branch_name, self.task.base_branch)
        rebase_note = ""
        if comparison.has_conflicts or comparison.behind > 0:
            async with self.workspace_service.allocate_workspace(self.task) as allocation:
                async for _ in self.workspace_service.prepare_workspace(self.task, allocation.slot):
                    pass
                rebase_result = await execute_rebase_with_result(self.task)

            if not rebase_result.success:
                if rebase_result.rebase_complete:
                    # STASH_CONFLICT: rebase committed but stash restore conflicted — no further rebase needed
                    pr_instructions = self._build_prompt(
                        self.task.codebase.merge_method,
                        "(git status available once stash conflicts are resolved)",
                    )
                    return _build_rebase_conflict_prompt(
                        rebase_result, "Once stash conflicts are resolved:", pr_instructions
                    )
                else:
                    # CONFLICT: rebase still in progress
                    pr_instructions = self._build_prompt(
                        self.task.codebase.merge_method, "(git status will be available once rebase is complete)"
                    )
                    return _build_rebase_conflict_prompt(rebase_result, "Once the rebase is complete:", pr_instructions)

            rebase_note = f"The task branch was rebased onto `{self.task.base_branch}` before creating the PR.\n\n"

        # Note: last_used_worktree_slot is accessed after workspace release but before reallocation;
        # reads are safe within the same request as reallocation requires another task to claim the slot.
        changes_context = await _get_task_changes_prompt_context(self.task)
        prompt = self._build_prompt(self.task.codebase.merge_method, changes_context)
        return rebase_note + prompt if rebase_note else prompt


class MergeAndFinaliseAction(TaskWorkflowAction):
    """Merge an open PR via GitHub and complete the task."""

    KEY = "task.merge_and_finalise"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return task.status == TaskStatus.PR_OPEN and task.github_pr_number is not None

    async def run(self) -> str | None:
        github = self.integration_service.get_integration_instance(GitHubIntegration)
        connection_result = await github.test_connection()
        if not connection_result.success:
            raise GitHubConnectionError(f"GitHub connection failed: {connection_result.message}")

        changes_context = await _get_task_changes_prompt_context(self.task)
        git_status = wrap_system_message(f"## Git Status\n{changes_context}", "git_status")
        instructions = (
            _FINALISATION_INSTRUCTIONS.replace("commit messages first.", "commit messages and push them first.")
            + "\n\nOnce all changes are committed and pushed, use the `merge_pr_and_finalise` tool to merge the PR and complete the task. "
            + _CHANGE_SUMMARY_PROMPT_GUIDANCE
        )
        return git_status + "\n\n" + instructions


class FinaliseAction(TaskWorkflowAction):
    """Complete a task when manual branch handling is configured (no merge needed)."""

    KEY = "task.finalise"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return task.status == TaskStatus.IMPLEMENTING and task.codebase.branch_handling == BranchHandling.MANUAL.value

    async def run(self) -> str | None:
        self.task_service.transition_to_complete(self.task)
        self.conversation_repo.commit()
        return None


class ArchiveTaskAction(TaskWorkflowAction):
    """Archive a task after the finalisation phase is complete."""

    KEY = "task.archive"

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return task.status == TaskStatus.MERGED

    async def run(self) -> str | None:
        self.task_service.transition_to_complete(self.task, method="archive")
        self.conversation_repo.commit()
        return None
