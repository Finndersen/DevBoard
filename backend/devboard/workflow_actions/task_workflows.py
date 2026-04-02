from devboard.agents.roles.context_helpers import build_execution_graph_context
from devboard.db.models import ParentEntityType, Task
from devboard.db.models.codebase import BranchHandling, MergeMethod
from devboard.db.models.conversation import AgentRoleType
from devboard.db.models.task import TaskStatus
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_git_service import TaskGitService
from devboard.workflow_actions.base import TaskWorkflowAction


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

    PROMPT_TEMPLATE = "The implementation plan has been approved. Review the plan and begin execution — use `execute_implementation_step` to run each step, consulting the execution graph below to identify steps that can run in parallel."

    @classmethod
    def is_available(cls, task: Task) -> bool:
        if task.status != TaskStatus.PLANNING:
            return False
        # Structured plan: must exist with pending status
        if task.implementation_plan_structured:
            return task.implementation_plan_structured.status == "pending"
        # Legacy Document plan
        return task.implementation_plan_id is not None

    async def run(self) -> str | None:
        self.task_service.transition_to_implementing(self.task)
        self.conversation_service.replace_active_conversation(
            entity_type=ParentEntityType.TASK,
            entity_id=self.task.id,
            new_agent_role=AgentRoleType.TASK_IMPLEMENTATION,
        )
        self.conversation_repo.commit()
        prompt = self.PROMPT_TEMPLATE
        execution_graph = build_execution_graph_context(self.task, include_step_status=False)
        if execution_graph:
            prompt += "\n\n" + execution_graph
        return prompt


class RebaseTaskBranchAction(TaskWorkflowAction):
    """Rebases a task's feature branch onto its base branch.

    Behavior varies by task status:
    - PLANNING: Direct service call (no agent involvement, no file changes expected)
    - IMPLEMENTING: Delegates to agent with rebase_task_branch tool for conflict resolution
    """

    KEY = "task.rebase_branch"

    IMPLEMENTING_PROMPT = """Use the `rebase_task_branch` tool to rebase this task's feature branch onto the base branch.

The tool handles stashing any uncommitted changes automatically — no need to check git status or stash manually beforehand.

The tool is idempotent - if a rebase is already in progress, it will continue it.
If you encounter merge conflicts:
1. The tool will tell you which files have conflicts
2. Edit those files to resolve the conflicts (remove conflict markers, keep correct code)
3. Stage the resolved files with `git add`
4. Call the `rebase_task_branch` tool again to continue

Keep using the tool until the rebase completes successfully."""

    BASE_BRANCH_CHANGES_PROMPT_TEMPLATE = """The task branch has been rebased onto the latest base branch.

{changes_summary}

Please briefly review these changes and note if any are relevant to the current task."""

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return task.status in (TaskStatus.PLANNING, TaskStatus.IMPLEMENTING)

    async def run(self) -> str | None:
        if self.task.status == TaskStatus.PLANNING:
            return await self._run_direct_rebase()
        else:
            return self.IMPLEMENTING_PROMPT

    async def _run_direct_rebase(self) -> str | None:
        """Execute direct rebase for PLANNING state (no file changes expected)."""
        rebase_result = await TaskGitService.rebase_task_branch(self.task)

        if rebase_result.outcome.value == "conflict":
            conflicted = ", ".join(rebase_result.conflicted_files or [])
            raise ValueError(f"Rebase encountered conflicts. Conflicted files: {conflicted}")

        # If base branch had changes, return prompt for agent to review them
        if rebase_result.base_branch_changes:
            return self.BASE_BRANCH_CHANGES_PROMPT_TEMPLATE.format(
                changes_summary=rebase_result.base_branch_changes.format_summary(self.task.base_branch),
            )

        return None


_FINALISATION_PREAMBLE = """## Git Status
{changes_context}

## Instructions
IMPORTANT: The git status above already contains the current branch state including commits and uncommitted changes. Do NOT run git status, git log, or git diff commands to inspect the branch — use the information provided above.

If there are uncommitted changes, create appropriate commit(s) using `git add -A && git commit -m "..."` with clear commit messages first."""


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
        return f"""## Git Status
{changes_context}

## Instructions
IMPORTANT: The git status above already contains the current branch state including commits and uncommitted changes. Do NOT run git status, git log, or git diff commands to inspect the branch — use the information provided above.

{commit_instruction}

Once all changes are committed, use the `complete_task_with_local_merge` tool to merge the feature branch and complete the task. Include a change_summary with:
- A brief overview of what was implemented
- Key files that were added or modified
- Any notable implementation decisions or trade-offs
- Testing considerations or known limitations"""

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
        changes_context = await _get_task_changes_prompt_context(self.task)
        return self._build_prompt(self.task.codebase.merge_method, changes_context)


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
        return (
            f"""## Git Status
{changes_context}

## Instructions
IMPORTANT: The git status above already contains the current branch state including commits and uncommitted changes. Do NOT run git status, git log, or git diff commands to inspect the branch — use the information provided above.

{commit_instruction}"""
            + ApproveAndCreatePRAction._PR_INSTRUCTIONS
        )

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
            raise ValueError(f"GitHub connection failed: {connection_result.message}")

        changes_context = await _get_task_changes_prompt_context(self.task)
        return self._build_prompt(self.task.codebase.merge_method, changes_context)


class MergeAndFinaliseAction(TaskWorkflowAction):
    """Merge an open PR via GitHub and complete the task."""

    KEY = "task.merge_and_finalise"
    PROMPT_TEMPLATE = (
        _FINALISATION_PREAMBLE.replace(
            "commit messages first.",
            "commit messages and push them first.",
        )
        + """

Once all changes are committed and pushed, use the `merge_pr_and_complete_task` tool to merge the PR and complete the task. Include a change_summary with:
- A brief overview of what was implemented
- Key files that were added or modified
- Any notable implementation decisions or trade-offs
- Testing considerations or known limitations"""
    )

    @classmethod
    def is_available(cls, task: Task) -> bool:
        return task.status == TaskStatus.PR_OPEN and task.github_pr_number is not None

    async def run(self) -> str | None:
        github = self.integration_service.get_integration_instance(GitHubIntegration)
        connection_result = await github.test_connection()
        if not connection_result.success:
            raise ValueError(f"GitHub connection failed: {connection_result.message}")

        changes_context = await _get_task_changes_prompt_context(self.task)
        return self.PROMPT_TEMPLATE.format(changes_context=changes_context)


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
