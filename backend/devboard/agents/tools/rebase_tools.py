"""Tools for rebase operations."""

from dataclasses import dataclass

from pydantic_ai import ModelRetry, Tool

from devboard.db.models import Task
from devboard.db.models.task import NoWorktreeAllocatedException
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.types import GitLogEntry
from devboard.services.task_git.types import RebaseOutcome, TaskConfigurationError
from devboard.services.task_git_service import BaseBranchChanges, TaskGitService


@dataclass
class RebaseActionResult:
    """Result of executing a rebase action."""

    success: bool
    message: str
    has_base_changes: bool = False
    # False only when a CONFLICT occurs mid-rebase (rebase is still in progress).
    # True for SUCCESS and STASH_CONFLICT (rebase committed, stash restore conflicted).
    rebase_complete: bool = True


def _format_commit_details(commits: list[GitLogEntry]) -> str:
    """Format commit details including subject and body for display."""
    if not commits:
        return ""

    lines = []
    for commit in commits:
        lines.append(f"  - **{commit.hash[:7]}**: {commit.subject}")
        if commit.body:
            # Indent each line of the body
            body_lines = commit.body.strip().split("\n")
            for body_line in body_lines:
                lines.append(f"    {body_line}")
    return "\n".join(lines)


async def _get_commits_for_conflicted_files(
    base_branch_changes: BaseBranchChanges,
    conflicted_files: list[str],
    repo_path: str,
) -> list[GitLogEntry]:
    """Get base branch commits that touched any of the conflicting files."""
    git = GitRepoIntegration(repo_path)
    commits = await git.get_commits_in_range(
        base_branch_changes.fork_point,
        base_branch_changes.base_head,
        file_paths=conflicted_files,
    )
    return commits


async def execute_rebase_with_result(task: Task) -> RebaseActionResult:
    """Execute a rebase for the given task and return a structured result.

    Calls TaskGitService.rebase_task_branch() and formats the outcome into
    a RebaseActionResult for consumption by tools and workflow actions.

    Args:
        task: The task whose branch should be rebased

    Raises:
        TaskConfigurationError: If the task has no branch configured
        NoWorktreeAllocatedException: If the task has no workspace allocated
    """
    result = await TaskGitService.rebase_task_branch(task)

    if result.outcome == RebaseOutcome.SUCCESS:
        message = f"Rebase completed successfully. New HEAD: {result.new_head}"

        if result.base_branch_changes:
            message += f"\n\n{result.base_branch_changes.format_summary(task.base_branch, task_file_paths=set(result.task_files_changed))}"
            message += "\n\nPlease review these changes and note if any are relevant to the current task."

        return RebaseActionResult(
            success=True, message=message, has_base_changes=result.base_branch_changes is not None
        )

    elif result.outcome == RebaseOutcome.CONFLICT:
        conflict_list = (
            "\n".join(f"  - {f}" for f in result.conflicted_files) if result.conflicted_files else "  (unknown)"
        )

        stash_note = ""
        if result.has_pending_stash:
            stash_note = (
                "\n\n**Note:** Uncommitted changes were stashed before rebase. "
                "They will be restored after the rebase completes successfully."
            )

        commit_details_section = ""
        if result.base_branch_changes and result.conflicted_files:
            relevant_commits = await _get_commits_for_conflicted_files(
                result.base_branch_changes,
                result.conflicted_files,
                result.slot_path,
            )
            if relevant_commits:
                formatted_commits = _format_commit_details(relevant_commits)
                commit_details_section = f"\n\n**Base branch commits that touched these files:**\n{formatted_commits}"

        message = (
            f"Rebase has conflicts that need to be resolved.\n\n"
            f"**Conflicted files:**\n{conflict_list}"
            f"{commit_details_section}\n\n"
            f"Please resolve the conflicts in these files (remove conflict markers, keep correct code), "
            f"then call this tool again to continue the rebase.{stash_note}"
        )
        return RebaseActionResult(success=False, message=message, rebase_complete=False)

    else:  # STASH_CONFLICT
        conflict_list = (
            "\n".join(f"  - {f}" for f in result.conflicted_files) if result.conflicted_files else "  (unknown)"
        )
        message = (
            f"Rebase completed successfully (new HEAD: {result.new_head}), but restoring your "
            f"uncommitted changes resulted in merge conflicts.\n\n"
            f"**Conflicted files:**\n{conflict_list}\n\n"
            f"Please resolve the conflicts in these files. Once resolved, "
            f"the rebase operation is complete."
        )
        return RebaseActionResult(success=False, message=message)


def create_rebase_task_branch_tool(
    task: Task,
) -> Tool:
    """Create an idempotent tool for rebasing a task's branch onto its base branch.

    This tool handles the complete rebase lifecycle:
    - If rebase is already in progress: attempts to continue
    - If no rebase in progress: starts new rebase (stashing uncommitted changes first)
    - On conflict: returns error details for agent to resolve, then call again
    - On success: applies stashed changes (if any), returns success

    Args:
        task: The task whose branch should be rebased
    """

    async def rebase_task_branch() -> str:
        """Rebase the task's feature branch onto its base branch.

        This tool is idempotent - you can call it multiple times safely:
        - If a rebase is in progress, it will attempt to continue
        - If no rebase is in progress, it will start a new rebase
        - If there are uncommitted changes, they will be stashed and restored after

        After resolving merge conflicts:
        1. Edit the conflicted files to resolve conflicts (remove conflict markers)
        2. Call this tool again to continue the rebase (staging is automatic)

        Returns:
            Success message with new HEAD commit hash

        Raises:
            ModelRetry: If rebase encounters conflicts or validation fails
        """
        try:
            result = await execute_rebase_with_result(task)
        except (TaskConfigurationError, NoWorktreeAllocatedException) as e:
            raise ModelRetry(str(e)) from e

        if result.success:
            return result.message

        raise ModelRetry(result.message)

    return Tool(function=rebase_task_branch, name="rebase_task_branch")  # ty:ignore[invalid-argument-type, invalid-return-type]
