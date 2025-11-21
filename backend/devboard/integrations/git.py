"""Git integration for repository operations."""

from pathlib import Path

import logfire

from .base import IntegrationConnectionResult
from .shell import execute_shell_command
from .types import BranchComparison, GitLogEntry, WorktreeInfo


class GitRepoIntegration:
    """
    Integration for Git operations on code repositories.
    Provides branch management, worktree operations, and repository analysis.
    """

    def __init__(self, repo_path: str | Path):
        """Initialize git integration.

        Args:
            repo_path: Path to the git repository root
        """
        self._repo_path = Path(repo_path).resolve()

    async def validate(self) -> IntegrationConnectionResult:
        """Test git repository access."""
        if not self._repo_path.exists():
            return IntegrationConnectionResult(
                success=False, message=f"Codebase path does not exist: {self._repo_path}"
            )

        if not self._repo_path.is_dir():
            return IntegrationConnectionResult(
                success=False, message=f"Codebase path is not a directory: {self._repo_path}"
            )

        git_dir = self._repo_path / ".git"
        if not git_dir.exists():
            return IntegrationConnectionResult(success=False, message=f"Not a git repository: {self._repo_path}")

        return IntegrationConnectionResult(success=True, message=f"Git repository accessible at: {self._repo_path}")

    async def _run_git_command(
        self,
        args: list[str],
        raise_on_error: bool = True,
        timeout: float = 30.0,
    ) -> str:
        """Run a git command in the codebase directory.

        Args:
            args: Git command arguments (without 'git' prefix)
            raise_on_error: Whether to raise exception on command failure
            timeout: Command timeout in seconds

        Returns:
            Stdout from the git command

        Raises:
            ShellCommandExecutionError: If git command fails and raise_on_error is True
        """
        result = await execute_shell_command(
            ["git"] + args,
            working_dir=self._repo_path,
            timeout=timeout,
            raise_on_error=raise_on_error,
        )
        return result.stdout.strip() if result.success else ""

    async def get_git_log(self, max_count: int = 10, file_path: str | None = None) -> list[GitLogEntry]:
        """Get git commit history.

        Args:
            max_count: Maximum number of commits to retrieve
            file_path: Optional file path to get history for specific file

        Returns:
            List of GitLogEntry objects
        """
        args = [
            "log",
            f"--max-count={max_count}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=iso",
        ]
        if file_path:
            args.append("--")
            args.append(file_path)

        output = await self._run_git_command(args)

        commits = []
        for line in output.split("\n"):
            if line.strip():
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    commits.append(
                        GitLogEntry(
                            hash=parts[0],
                            author=parts[1],
                            date=parts[2],
                            message=parts[3],
                        )
                    )

        return commits

    async def get_git_diff(
        self,
        commit1: str | None = None,
        commit2: str | None = None,
        file_path: str | None = None,
    ) -> str:
        """Get git diff between commits or working directory.

        Args:
            commit1: First commit hash/reference
            commit2: Second commit hash/reference (optional)
            file_path: Optional file path to get diff for specific file

        Returns:
            Diff output as string
        """
        args = ["diff"]
        if commit1:
            if commit2:
                args.append(f"{commit1}..{commit2}")
            else:
                args.append(commit1)

        if file_path:
            args.append("--")
            args.append(file_path)

        return await self._run_git_command(args)

    async def get_git_branches(self, remote: bool = False) -> list[str]:
        """Get list of git branches.

        Args:
            remote: Whether to list remote branches

        Returns:
            List of branch names
        """
        args = ["branch"]
        if remote:
            args.append("-r")

        output = await self._run_git_command(args)
        branches = []
        for line in output.split("\n"):
            branch = line.strip()
            if branch and not branch.startswith("*"):
                branches.append(branch)
            elif branch.startswith("* "):
                branches.append(branch[2:])

        return branches

    async def list_worktrees(self) -> list[WorktreeInfo]:
        """List all git worktrees for this repository.

        Returns:
            List of WorktreeInfo objects for each worktree

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        output = await self._run_git_command(["worktree", "list", "--porcelain"])

        worktrees = []
        current_worktree = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                if current_worktree:
                    # Determine if this is the main repository
                    is_main = current_worktree.get("path") == str(self._repo_path)
                    worktrees.append(
                        WorktreeInfo(
                            path=current_worktree["path"],
                            branch=current_worktree.get("branch", ""),
                            commit=current_worktree.get("HEAD", ""),
                            is_main=is_main,
                        )
                    )
                    current_worktree = {}
            elif line.startswith("worktree "):
                current_worktree["path"] = line[9:]
            elif line.startswith("HEAD "):
                current_worktree["HEAD"] = line[5:]
            elif line.startswith("branch "):
                # Remove "refs/heads/" prefix if present
                branch = line[7:]
                if branch.startswith("refs/heads/"):
                    branch = branch[11:]
                current_worktree["branch"] = branch

        # Handle last worktree if file doesn't end with blank line
        if current_worktree:
            is_main = current_worktree.get("path") == str(self._repo_path)
            worktrees.append(
                WorktreeInfo(
                    path=current_worktree["path"],
                    branch=current_worktree.get("branch", ""),
                    commit=current_worktree.get("HEAD", ""),
                    is_main=is_main,
                )
            )

        return worktrees

    async def create_worktree(self, path: str, branch: str) -> None:
        """Create a new git worktree.

        Args:
            path: Filesystem path for the new worktree
            branch: Branch to checkout in the worktree

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["worktree", "add", path, branch])

    async def remove_worktree(self, path: str, force: bool = False) -> None:
        """Remove a git worktree.

        Args:
            path: Path to the worktree to remove
            force: Force removal even with uncommitted changes

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        args = ["worktree", "remove", path]
        if force:
            args.append("--force")
        await self._run_git_command(args)

    async def create_branch(self, name: str, base: str = "HEAD") -> None:
        """Create a new git branch without checking it out.

        Args:
            name: Name of the new branch
            base: Base commit/branch to create from (default: HEAD)

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["branch", name, base])

    async def checkout_branch(self, name: str) -> None:
        """Checkout a git branch.

        Args:
            name: Name of the branch to checkout

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["checkout", name])

    async def delete_branch(self, name: str, force: bool = False) -> None:
        """Delete a git branch.

        Args:
            name: Name of the branch to delete
            force: Force deletion even if not fully merged

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        args = ["branch"]
        args.append("-D" if force else "-d")
        args.append(name)
        await self._run_git_command(args)

    async def get_current_branch(self) -> str:
        """Get the currently checked out branch name.

        Returns:
            Name of the current branch

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        return await self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])

    async def get_default_branch(self) -> str:
        """Get the repository's default remote-tracking branch.

        Returns the remote HEAD reference (e.g., 'origin/main' or 'origin/master').
        This remote-tracking branch can be used directly as a base for creating new branches.

        Returns:
            Remote-tracking branch reference (e.g., 'origin/main')

        Raises:
            Exception: If unable to determine default branch
        """
        output = await self._run_git_command(
            ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            raise_on_error=False,
            timeout=10.0,
        )

        if output:
            return output

        # If not set up, raise an error with helpful message
        logfire.error("origin/HEAD not set up - run 'git remote set-head origin --auto' to configure")
        raise Exception(
            "Unable to determine repository default branch. "
            "Run 'git remote set-head origin --auto' in the repository to set it up."
        )

    async def branch_exists(self, name: str) -> bool:
        """Check if a branch exists.

        Args:
            name: Name of the branch to check

        Returns:
            True if branch exists, False otherwise
        """
        output = await self._run_git_command(
            ["rev-parse", "--verify", f"refs/heads/{name}"],
            raise_on_error=False,
        )
        return bool(output)

    async def get_branch_comparison(self, branch: str, base: str) -> BranchComparison:
        """Get comparison information between a branch and its base.

        Args:
            branch: Branch to compare
            base: Base branch to compare against

        Returns:
            BranchComparison object with ahead/behind counts and conflict information
        """
        # Get ahead/behind counts
        ahead = 0
        behind = 0
        try:
            output = await self._run_git_command(["rev-list", "--left-right", "--count", f"{base}...{branch}"])
            parts = output.split()
            behind = int(parts[0]) if len(parts) > 0 else 0
            ahead = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            logfire.warning(f"Failed to parse branch comparison counts for {branch} vs {base}")

        # Check for merge conflicts using merge-tree
        has_conflicts = False
        try:
            # Get merge base
            merge_base = await self._run_git_command(["merge-base", base, branch])
            # Check for conflicts with merge-tree
            merge_tree_output = await self._run_git_command(["merge-tree", merge_base, base, branch])
            # If merge-tree output contains conflict markers, there are conflicts
            has_conflicts = "<<<<<<<" in merge_tree_output
        except Exception:
            # If merge-base fails, branches may not have common ancestor
            logfire.warning(f"Failed to check for merge conflicts between {branch} and {base}")
            has_conflicts = False

        return BranchComparison(
            ahead=ahead,
            behind=behind,
            has_conflicts=has_conflicts,
            can_merge=ahead > 0 and not has_conflicts,
        )

    async def merge_branch(self, source: str, target: str, no_ff: bool = False) -> str:
        """Merge a source branch into a target branch.

        Args:
            source: Source branch to merge from
            target: Target branch to merge into
            no_ff: Create a merge commit even if fast-forward is possible

        Returns:
            Commit hash of the merge commit

        Raises:
            ShellCommandExecutionError: If merge fails
        """
        # First checkout the target branch
        await self.checkout_branch(target)

        # Perform the merge
        args = ["merge", source]
        if no_ff:
            args.append("--no-ff")
        await self._run_git_command(args)

        # Return the new HEAD commit hash
        return await self._run_git_command(["rev-parse", "HEAD"])

    async def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes in the working directory.

        Returns:
            True if there are uncommitted changes, False otherwise
        """
        output = await self._run_git_command(
            ["status", "--porcelain"],
            raise_on_error=False,
        )
        return bool(output)

    async def detect_git_remote_url(self) -> str | None:
        """Detect git remote URL for this repository.

        Returns:
            Remote URL if found, None otherwise
        """
        # Try to get "origin" remote URL
        output = await self._run_git_command(
            ["remote", "get-url", "origin"],
            raise_on_error=False,
            timeout=10.0,
        )

        if output:
            return output

        # If no origin, list all remotes and get URL of first remote
        remotes = await self._run_git_command(
            ["remote"],
            raise_on_error=False,
            timeout=10.0,
        )

        if remotes:
            first_remote = remotes.split("\n")[0]
            output = await self._run_git_command(
                ["remote", "get-url", first_remote],
                raise_on_error=False,
                timeout=10.0,
            )

            if output:
                return output

        return None
