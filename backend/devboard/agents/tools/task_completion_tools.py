"""Tools for task completion operations."""

from pydantic_ai import ModelRetry, Tool

from devboard.db.models import Task
from devboard.db.models.codebase import MergeMethod
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_git import BaseWorkdirOverlapError
from devboard.services.task_git.types import MergeFailureError, MergeOutcome, TaskConfigurationError
from devboard.services.task_service import TaskService


def create_complete_task_with_local_merge_tool(
    task: Task,
    task_service: TaskService,
) -> Tool:
    """Create a tool for completing a task via local merge.

    This tool validates preconditions, creates the change summary document,
    executes the merge strategy, and transitions the task to COMPLETE status.

    Args:
        task: The task to complete
        task_service: Service for task operations (includes merge logic)
    """

    async def complete_task_with_local_merge(change_summary: str) -> str:
        """Complete the task by merging the feature branch locally.

        This tool will:
        1. Validate that all changes are committed (git state is clean)
        2. Save the change summary document
        3. Merge the feature branch into the base branch using the configured merge strategy
        4. Delete the feature branch
        5. Transition the task to COMPLETE status

        IMPORTANT: Before calling this tool, ensure all changes are committed
        (no uncommitted changes in workspace).

        Args:
            change_summary: Markdown content summarizing the changes made. Include:
                - A brief overview of what was implemented
                - Key files that were added or modified
                - Any notable implementation decisions or trade-offs
                - Testing considerations or known limitations

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

        # Execute merge and transition to complete (creates change_summary document)
        try:
            merge_result = await task_service.complete_task_with_local_merge(task, change_summary)
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
                    "3. Then call complete_task_with_local_merge() again"
                )
            raise ModelRetry(error_msg) from e
        except TaskConfigurationError as e:
            raise ModelRetry(str(e)) from e

        result = f"Task completed successfully. {merge_result.message}"
        if merge_result.merge_commit:
            result += f" Merge commit: {merge_result.merge_commit}"
        return result

    return Tool(function=complete_task_with_local_merge, name="complete_task_with_local_merge")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_merge_pr_and_complete_task_tool(
    task: Task,
    task_service: TaskService,
    github_integration: GitHubIntegration,
) -> Tool:
    """Create a tool for merging a PR and completing the task.

    This tool merges the PR via GitHub API, then handles cleanup (branch deletion,
    change summary creation) and task status transition.

    Args:
        task: The task to complete
        task_service: Service for task operations
        github_integration: GitHub integration for API calls
    """

    async def merge_pr_and_complete_task(change_summary: str) -> str:
        """Merge the pull request and complete the task.

        This tool will:
        1. Validate that all changes are committed (git state is clean)
        2. Merge the pull request via GitHub using the configured merge method (squash, rebase, or merge commit)
        3. Save the change summary document
        4. Delete the local feature branch
        5. Transition the task to COMPLETE status

        IMPORTANT: Before calling this tool, ensure all changes are committed and pushed
        (no uncommitted changes in workspace).

        Args:
            change_summary: Markdown content summarizing the changes made. Include:
                - A brief overview of what was implemented
                - Key files that were added or modified
                - Any notable implementation decisions or trade-offs
                - Testing considerations or known limitations

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

        # If PR is already merged (e.g., merged directly on GitHub), skip merge but still complete task
        if pr_status.merged:
            try:
                await task_service.complete_pr_task(task, change_summary)
            except ValueError as e:
                raise ModelRetry(str(e)) from e
            return "Task completed successfully. PR was already merged on GitHub."

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

        # Complete the task (creates change summary, deletes branch, transitions status)
        try:
            await task_service.complete_pr_task(task, change_summary)
        except ValueError as e:
            raise ModelRetry(str(e)) from e

        result = f"Task completed successfully. PR merged via {merge_method.value}. Merge commit: {merge_result.sha}"
        return result

    return Tool(function=merge_pr_and_complete_task, name="merge_pr_and_complete_task")  # ty:ignore[invalid-argument-type, invalid-return-type]
