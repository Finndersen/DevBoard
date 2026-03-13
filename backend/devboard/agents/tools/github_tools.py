"""GitHub-related tools for agent use."""

from pydantic_ai import ModelRetry, Tool

from devboard.db.models.task import Task
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.github import CommentThread, GitHubIntegration, ReviewComment, ReviewWithComments
from devboard.services.task_service import TaskService


def create_github_pr_tool(
    task: Task,
    github_integration: GitHubIntegration,
    task_service: TaskService,
) -> Tool:
    """Create a tool for creating GitHub pull requests for a task.

    This tool allows the agent to:
    1. Push the task branch to remote (if not already pushed)
    2. Create a GitHub PR with a title and description
    3. Transition task to PR_OPEN status (includes creating TASK_PR_REVIEW conversation)

    The tool is idempotent - if a PR already exists for this branch on GitHub,
    it will skip creation and continue with the transition.

    Args:
        task: The task to create a PR for
        github_integration: GitHub integration for API calls
        task_service: Service for task operations (handles transition and conversation)
    """

    async def create_pull_request(
        title: str,
        body: str,
    ) -> str:
        """Create a GitHub pull request for this task.
        This will:
        1. Validate all changes are committed (fails if uncommitted changes exist)
        2. Push the current branch to the remote (if not already pushed)
        3. Create a pull request on GitHub
        4. Transition the task to PR_OPEN status
        5. Create a new conversation for PR review

        This tool is idempotent - if a PR was already created for this task, it will
        skip creation and complete the remaining steps.

        Args:
            title: The title for the pull request. Should be concise and descriptive.
            body: The body/description of the pull request. Use markdown formatting.
                  Include a summary of changes, any testing notes, and relevant context.

        Returns:
            A success message with the PR URL/number.

        Raises:
            ModelRetry: If validation fails or PR creation fails.
        """
        # Validate codebase has GitHub remote
        if not task.codebase.repository_url:
            raise ModelRetry("Codebase has no GitHub remote configured. Cannot create PR.")

        # Validate git state is clean
        workspace_dir = task.get_current_workspace_dir()
        git = GitRepoIntegration(workspace_dir)
        if await git.has_uncommitted_changes():
            raise ModelRetry(
                "Cannot create PR - workspace has uncommitted changes. "
                "Please commit all changes before creating the pull request."
            )

        # Fetch latest remote state so conflict check is against up-to-date base branch
        main_git = GitRepoIntegration(task.codebase.local_path)
        try:
            await main_git.fetch()
        except Exception:
            pass  # Fetch failure is non-fatal - continue with local state

        # Check for merge conflicts with base branch
        comparison = await main_git.get_branch_comparison(task.branch_name, task.base_branch)
        if comparison.has_conflicts:
            raise ModelRetry(
                "Cannot create PR: merge conflicts detected between the feature branch and base branch. "
                "Please call rebase_task_branch() to rebase onto the base branch and resolve conflicts, "
                "then call create_pull_request() again."
            )

        try:
            # Get repository wrapper (API call happens here)
            github_repo = await github_integration.get_repository_from_url(task.codebase.repository_url)

            # Check if PR already exists on GitHub (idempotent - handles retry after partial failure)
            existing_pr = await github_repo.find_pull_request_for_branch(task.branch_name)
            if existing_pr:
                pr_number = existing_pr.number
            else:
                # Push branch to remote (safe even if already up-to-date)
                await git.push_branch(task.branch_name, set_upstream=True)

                # Create PR via GitHub API
                pr = await github_repo.create_pull_request(
                    title=title,
                    body=body,
                    head=task.branch_name,
                    base=task.base_branch.replace("origin/", ""),  # Remove origin/ prefix if present
                )
                pr_number = pr.number

            # Store PR number on task (may already be set, but ensures consistency)
            task.github_pr_number = pr_number

        except Exception as e:
            raise ModelRetry(f"Failed to create pull request: {e}") from e

        # Transition task to PR_OPEN (also creates TASK_PR_REVIEW conversation and commits)
        task_service.transition_to_pr_open(task, pr_number)

        return f"Successfully created PR #{pr_number}. Task transitioned to PR_OPEN status."

    return Tool(
        function=create_pull_request,
        name="create_pull_request",
    )


def _format_comment(comment: ReviewComment, indent: str = "") -> str:
    """Format a single comment for markdown output."""
    lines = [f"{indent}**{comment.author}** at `{comment.path}`"]
    if comment.line:
        lines[0] += f" (line {comment.line})"
    lines[0] += ":"

    # Include diff hunk for context if available
    if comment.diff_hunk:
        lines.append(f"{indent}```diff")
        lines.append(f"{indent}{comment.diff_hunk}")
        lines.append(f"{indent}```")

    lines.append(f"{indent}{comment.body}")
    return "\n".join(lines)


def _format_thread(thread: CommentThread, indent: str = "") -> str:
    """Format a comment thread for markdown output."""
    lines = [_format_comment(thread.original, indent)]

    for reply in thread.replies:
        lines.append("")
        lines.append(f"{indent}  > **Reply by {reply.author}:**")
        lines.append(f"{indent}  > {reply.body}")

    return "\n".join(lines)


def _format_review(review: ReviewWithComments) -> str:
    """Format a review with its comment threads for markdown output."""
    lines = [
        f"## Review by {review.author}",
        f"**State:** {review.state}",
    ]

    if review.submitted_at:
        lines.append(f"**Submitted:** {review.submitted_at}")

    if review.body:
        lines.append(f"\n{review.body}")

    if review.comment_threads:
        lines.append(f"\n### Code Comments ({len(review.comment_threads)} threads)")
        for thread in review.comment_threads:
            lines.append("")
            lines.append(_format_thread(thread, ""))

    return "\n".join(lines)


def create_get_pr_feedback_tool(task: Task, github_integration: GitHubIntegration) -> Tool:
    """Create a tool for fetching comprehensive PR feedback.

    Combines reviews and comments into a structured view:
    - Reviews with their associated code comments grouped into threads
    - Standalone comments (not part of a formal review) also grouped into threads

    Args:
        task: Task instance with github_pr_number set
        github_integration: GitHub integration for API calls
    """

    async def get_pr_feedback() -> str:
        """Fetch all PR feedback including reviews and code comments.

        Returns a comprehensive view of all PR feedback:
        - Reviews with their state (APPROVED, CHANGES_REQUESTED, etc.)
        - Code comments associated with each review, grouped into threads
        - Standalone code comments not part of any formal review

        Comments are organized into threads showing the original comment
        and all replies. Use this to understand all reviewer feedback
        and the discussions around specific code changes.
        """
        # Validate prerequisites
        if not task.github_pr_number or not task.codebase.repository_url:
            return "Error: Task does not have PR number or repository URL configured."

        # Fetch PR and feedback (API calls happen here)
        try:
            github_repo = await github_integration.get_repository_from_url(task.codebase.repository_url)
            github_pr = await github_repo.get_pull_request(task.github_pr_number)
            feedback = await github_pr.get_feedback()
        except Exception as e:
            return f"Error fetching PR feedback: {e}"

        if not feedback.reviews and not feedback.standalone_threads:
            return "No reviews or comments found for this PR."

        sections = []

        # Format reviews
        if feedback.reviews:
            sections.append("# Reviews")
            for review in feedback.reviews:
                sections.append("")
                sections.append(_format_review(review))
                sections.append("\n---")

        # Format standalone threads
        if feedback.standalone_threads:
            sections.append("\n# Standalone Comments")
            sections.append("(Comments not associated with a formal review)")

            for thread in feedback.standalone_threads:
                sections.append("")
                sections.append(_format_thread(thread, ""))
                sections.append("")

        return "\n".join(sections)

    return Tool(function=get_pr_feedback, name="get_pr_feedback")
