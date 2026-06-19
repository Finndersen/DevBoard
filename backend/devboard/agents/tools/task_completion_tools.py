"""Tools for task completion operations."""

import logfire
from pydantic_ai import ModelRetry, Tool

from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.registry import get_execution_manager
from devboard.db.models import Task
from devboard.db.models.codebase import MergeMethod
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_git import BaseWorkdirOverlapError
from devboard.services.task_git.types import MergeFailureError, MergeOutcome, TaskConfigurationError
from devboard.services.task_service import TaskService

FINALISATION_PROMPT = "The code has been merged. Review the change summary and propose a structured plan of all follow-up tasks before taking any action."


def create_merge_branch_and_finalise_tool(
    task: Task,
    task_service: TaskService,
) -> Tool:
    """Create a tool for merging a task branch locally and finalising the task.

    This tool validates preconditions, creates the change summary document,
    executes the merge strategy, and transitions the task to MERGED status.

    Args:
        task: The task to merge
        task_service: Service for task operations (includes merge logic)
    """

    async def merge_branch_and_finalise(change_summary: str) -> str:
        """Merge the feature branch locally and transition to MERGED status.

        This tool will:
        1. Validate that all changes are committed (git state is clean)
        2. Save the change summary document
        3. Merge the feature branch into the base branch using the configured merge strategy
        4. Delete the feature branch
        5. Transition the task to MERGED status
        6. Replace active conversation with TASK_FINALISATION agent

        IMPORTANT: Before calling this tool, ensure all changes are committed
        (no uncommitted changes in workspace).

        Args:
            change_summary: Concise Markdown document summarising what was delivered. Group changes
                by type — omit empty categories:
                - **Functional**: New features or behaviours (reference spec requirements met)
                - **Bug Fix**: Issues resolved
                - **Optimisation**: Performance or efficiency improvements
                - **Refactor/Cleanup**: Internal restructuring without behaviour change
                - **Cosmetic**: UI/style-only changes
                If anything deviates from the agreed specification (scope reduced, approach changed,
                requirement deferred), include a **Deviations from Specification** section — the most
                critical thing to capture accurately. Omit if fully on-spec.
                Optionally include a **Learnings** section for non-obvious discoveries made during
                implementation not captured in the spec — unexpected constraints, useful patterns,
                caveats — that may be valuable for follow-up tasks or documentation updates.

        Returns:
            Success message with merge details.

        Raises:
            ModelRetry: If validation fails or merge fails.
        """
        # Validate git state is clean
        workspace_dir = task.get_current_workspace_dir()
        git = GitRepoIntegration(workspace_dir)
        if await git.has_uncommitted_changes():
            raise ModelRetry(
                "Cannot merge - workspace has uncommitted changes. "
                "Please commit all changes before completing the task."
            )

        # Execute merge and transition to merged (creates change_summary document)
        try:
            merge_result, new_conv_id = await task_service.merge_task_branch(task, change_summary)
        except BaseWorkdirOverlapError as e:
            return f"{e}\n\nSTOP. Inform the user that they need to commit or stash their uncommitted changes before this task can be merged."
        except MergeFailureError as e:
            error_msg = str(e)
            if e.outcome == MergeOutcome.CONFLICT:
                error_msg += (
                    "\n\nThe feature branch has NOT been modified - it is still in a clean state. "
                    "To resolve this:\n"
                    "1. Call rebase_task_branch() to rebase the feature branch onto the latest base branch\n"
                    "2. If there are conflicts, resolve them manually\n"
                    "3. Then call merge_branch_and_finalise() again"
                )
            raise ModelRetry(error_msg) from e
        except TaskConfigurationError as e:
            raise ModelRetry(str(e)) from e

        try:
            get_execution_manager().start_agent_execution(new_conv_id, FINALISATION_PROMPT)
        except (AssertionError, ConversationBusyError) as e:
            logfire.warning("Failed to auto-start finalisation agent after merge", error=str(e))

        result = f"Task merged successfully. {merge_result.message}"
        if merge_result.merge_commit:
            result += f" Merge commit: {merge_result.merge_commit}"
        return result

    return Tool(function=merge_branch_and_finalise, name="merge_branch_and_finalise")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_merge_pr_and_finalise_tool(
    task: Task,
    task_service: TaskService,
    github_integration: GitHubIntegration,
) -> Tool:
    """Create a tool for merging a PR and finalising the task.

    This tool merges the PR via GitHub API, then handles cleanup (branch deletion,
    change summary creation) and task status transition to MERGED.

    Args:
        task: The task to merge
        task_service: Service for task operations
        github_integration: GitHub integration for API calls
    """

    async def merge_pr_and_finalise(change_summary: str) -> str:
        """Merge the pull request and transition to MERGED status.

        This tool will:
        1. Validate that all changes are committed (git state is clean)
        2. Merge the pull request via GitHub using the configured merge method (squash, rebase, or merge commit)
        3. Save the change summary document
        4. Delete the local feature branch
        5. Transition the task to MERGED status
        6. Replace active conversation with TASK_FINALISATION agent

        IMPORTANT: Before calling this tool, ensure all changes are committed and pushed
        (no uncommitted changes in workspace).

        Args:
            change_summary: Concise Markdown document summarising what was delivered. Group changes
                by type — omit empty categories:
                - **Functional**: New features or behaviours (reference spec requirements met)
                - **Bug Fix**: Issues resolved
                - **Optimisation**: Performance or efficiency improvements
                - **Refactor/Cleanup**: Internal restructuring without behaviour change
                - **Cosmetic**: UI/style-only changes
                If anything deviates from the agreed specification (scope reduced, approach changed,
                requirement deferred), include a **Deviations from Specification** section — the most
                critical thing to capture accurately. Omit if fully on-spec.
                Optionally include a **Learnings** section for non-obvious discoveries made during
                implementation not captured in the spec — unexpected constraints, useful patterns,
                caveats — that may be valuable for follow-up tasks or documentation updates.

        Returns:
            Success message with merge details.

        Raises:
            ModelRetry: If validation fails or merge fails.
        """
        if not task.github_pr_number:
            raise ModelRetry(f"Task {task.id} has no PR configured")

        if not task.codebase.repository_url:
            raise ModelRetry("Codebase has no GitHub remote configured. Cannot merge PR.")

        # Validate git state is clean
        workspace_dir = task.get_current_workspace_dir()
        git = GitRepoIntegration(workspace_dir)
        if await git.has_uncommitted_changes():
            raise ModelRetry(
                "Cannot merge PR - workspace has uncommitted changes. "
                "Please commit and push all changes before completing the task."
            )

        # Get GitHub PR
        try:
            github_repo = await github_integration.get_repository_from_url(task.codebase.repository_url)
            github_pr = await github_repo.get_pull_request(task.github_pr_number)
        except Exception as e:
            return f"Error fetching PR from GitHub: {e}"

        # Check PR status before attempting merge
        pr_status = await github_pr.get_status()

        # If PR is already merged (e.g., merged directly on GitHub), skip merge but still finalise task
        if pr_status.merged:
            try:
                new_conv_id = await task_service.merge_pr_task(task, change_summary)
            except ValueError as e:
                raise ModelRetry(str(e)) from e
            try:
                get_execution_manager().start_agent_execution(new_conv_id, FINALISATION_PROMPT)
            except (AssertionError, ConversationBusyError) as e:
                logfire.warning("Failed to auto-start finalisation agent after merge", error=str(e))
            return "Task merged successfully. PR was already merged on GitHub."

        # PR must be open to merge
        if pr_status.state != "open":
            raise ModelRetry(f"PR is not open (state: {pr_status.state}).")

        # Check if PR is mergeable
        if pr_status.mergeable is False:
            # Provide detailed error based on mergeable_state
            state_messages = {
                "dirty": "PR has merge conflicts that must be resolved first.",
                "blocked": "PR is blocked by branch protection rules.",
                "behind": "PR branch is behind the base branch and needs to be updated.",
                "unstable": "PR has failing CI checks.",
            }
            message = state_messages.get(
                pr_status.mergeable_state or "",
                f"PR is not mergeable (state: {pr_status.mergeable_state}).",
            )
            raise ModelRetry(f"Cannot merge PR: {message}")

        # Get merge method from codebase configuration
        merge_method = MergeMethod(task.codebase.merge_method)

        # Merge PR via GitHub
        try:
            merge_result = await github_pr.merge(merge_method=merge_method)
        except Exception as e:
            raise ModelRetry(f"Failed to merge PR: {e}") from e

        if not merge_result.merged:
            raise ModelRetry(f"PR merge was not successful: {merge_result.message}")

        # Merge the task (creates change summary, deletes branch, transitions status)
        try:
            new_conv_id = await task_service.merge_pr_task(task, change_summary)
        except ValueError as e:
            raise ModelRetry(str(e)) from e

        try:
            get_execution_manager().start_agent_execution(new_conv_id, FINALISATION_PROMPT)
        except (AssertionError, ConversationBusyError) as e:
            logfire.warning("Failed to auto-start finalisation agent after merge", error=str(e))

        result = f"Task merged successfully. PR merged via {merge_method.value}. Merge commit: {merge_result.sha}"
        return result

    return Tool(function=merge_pr_and_finalise, name="merge_pr_and_finalise")  # ty:ignore[invalid-argument-type, invalid-return-type]
