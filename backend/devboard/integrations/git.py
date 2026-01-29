"""Git integration for repository operations."""

import re
from pathlib import Path

import logfire

from .base import IntegrationConnectionResult
from .shell import RebaseConflictError, ShellCommandExecutionError, execute_shell_command
from .types import (
    BranchComparison,
    BranchReleaseResult,
    CommitDiff,
    FileDiff,
    GitLogEntry,
    StructuredDiff,
    WorktreeInfo,
)


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

    async def get_merge_base(self, branch1: str, branch2: str) -> str:
        """Get the merge base (common ancestor) between two branches.

        Args:
            branch1: First branch/commit reference
            branch2: Second branch/commit reference

        Returns:
            Commit hash of the merge base
        """
        return await self._run_git_command(["merge-base", branch1, branch2])

    async def get_fork_point(self, base_branch: str, feature_branch: str) -> str | None:
        """Get the fork point where feature branch diverged from base branch.

        Uses git merge-base to find the common ancestor commit between the two branches.
        This works reliably for the standard case of a feature branch created from a base
        branch, even when the base branch has had more commits added since.

        Args:
            base_branch: The base branch (e.g., 'main', 'master')
            feature_branch: The feature branch to find fork point for

        Returns:
            Commit hash of the fork point, or None if it cannot be determined
        """
        merge_base = await self._run_git_command(
            ["merge-base", base_branch, feature_branch],
            raise_on_error=False,
        )

        logfire.debug(
            "get_fork_point result",
            base_branch=base_branch,
            feature_branch=feature_branch,
            merge_base=merge_base,
            repo_path=str(self._repo_path),
        )

        return merge_base if merge_base else None

    async def get_commits_in_range(self, base_commit: str, head_commit: str) -> list[GitLogEntry]:
        """Get commits in a range (base..head).

        Args:
            base_commit: Base commit hash/reference (exclusive)
            head_commit: Head commit hash/reference (inclusive)

        Returns:
            List of GitLogEntry objects for commits in the range
        """
        args = [
            "log",
            f"{base_commit}..{head_commit}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=iso",
        ]

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

    async def get_commit_diff(self, commit_hash: str) -> str:
        """Get the diff for a specific commit.

        Args:
            commit_hash: Commit hash to get diff for

        Returns:
            Diff output as string
        """
        return await self._run_git_command(["show", "--format=", commit_hash])

    def _parse_git_diff(self, raw_diff: str) -> StructuredDiff:
        """Parse raw git diff output into structured per-file diffs.

        Args:
            raw_diff: Raw git diff output

        Returns:
            StructuredDiff with parsed files and stats
        """
        if not raw_diff.strip():
            return StructuredDiff(files=[], additions=0, deletions=0)

        files: list[FileDiff] = []

        # Split by file headers (diff --git lines)
        file_blocks = re.split(r"(?=^diff --git)", raw_diff, flags=re.MULTILINE)

        for block in file_blocks:
            block = block.strip()
            if not block:
                continue

            # Extract file path from +++ b/path line
            file_path_match = re.search(r"^\+\+\+ b/(.+)$", block, re.MULTILINE)
            if not file_path_match:
                # Try --- a/path for deletions
                file_path_match = re.search(r"^--- a/(.+)$", block, re.MULTILINE)

            if not file_path_match:
                continue

            file_path = file_path_match.group(1)

            # Detect new file and deleted file status
            is_new_file = bool(re.search(r"^new file mode", block, re.MULTILINE))
            is_deleted = bool(re.search(r"^deleted file mode", block, re.MULTILINE))

            # Filter out git metadata lines from diff content
            # Remove: new file mode, deleted file mode, similarity index, rename from/to, etc.
            filtered_lines = []
            for line in block.split("\n"):
                # Skip metadata lines we want to hide
                if re.match(
                    r"^(new file mode|deleted file mode|similarity index|rename from|rename to|old mode|new mode)", line
                ):
                    continue
                filtered_lines.append(line)
            filtered_block = "\n".join(filtered_lines)

            # Count additions and deletions (lines starting with + or -, but not +++ or ---)
            additions = len(re.findall(r"^\+(?!\+\+)", filtered_block, re.MULTILINE))
            deletions = len(re.findall(r"^-(?!--)", filtered_block, re.MULTILINE))

            files.append(
                FileDiff(
                    file_path=file_path,
                    diff_content=filtered_block,
                    additions=additions,
                    deletions=deletions,
                    is_new_file=is_new_file,
                    is_deleted=is_deleted,
                )
            )

        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)

        return StructuredDiff(files=files, additions=total_additions, deletions=total_deletions)

    async def get_structured_diff(
        self,
        commit1: str | None = None,
        commit2: str | None = None,
    ) -> StructuredDiff:
        """Get structured git diff between commits or working directory.

        Args:
            commit1: First commit hash/reference
            commit2: Second commit hash/reference (optional)

        Returns:
            StructuredDiff with parsed files and stats
        """
        raw_diff = await self.get_git_diff(commit1=commit1, commit2=commit2)
        return self._parse_git_diff(raw_diff)

    async def get_structured_commit_diff(self, commit_hash: str) -> CommitDiff:
        """Get structured diff for a specific commit including metadata.

        Args:
            commit_hash: Commit hash to get diff for

        Returns:
            CommitDiff with commit metadata and parsed files
        """
        # Get commit metadata using show with format
        output = await self._run_git_command(
            [
                "show",
                "--no-patch",
                "--pretty=format:%H|%an|%ad|%s",
                "--date=iso",
                commit_hash,
            ]
        )

        parts = output.strip().split("|", 3)
        if len(parts) < 4:
            raise ValueError(f"Failed to get metadata for commit {commit_hash}")

        # Get and parse diff
        raw_diff = await self.get_commit_diff(commit_hash)
        structured = self._parse_git_diff(raw_diff)

        return CommitDiff(
            commit_hash=parts[0],
            author=parts[1],
            date=parts[2],
            message=parts[3],
            files=structured.files,
            additions=structured.additions,
            deletions=structured.deletions,
        )

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

    async def get_branch_head(self, branch: str) -> str | None:
        """Get the HEAD commit hash for a branch.

        Args:
            branch: Branch name (can be local like 'main' or remote like 'origin/main')

        Returns:
            The commit hash, or None if the branch doesn't exist
        """
        result = await self._run_git_command(
            ["rev-parse", "--verify", branch],
            raise_on_error=False,
        )
        return result if result else None

    async def get_default_branch(self) -> str:
        """Get the repository's default branch.

        Detection strategy:
        1. Try remote HEAD reference (origin/main, origin/master, etc.)
        2. Fall back to local HEAD (current branch for repos without remotes)
        3. Check for common branch names (main, master) as last resort

        Returns:
            Branch reference (e.g., 'origin/main' for repos with remotes,
            'main' for local-only repos)

        Raises:
            Exception: If unable to determine default branch
        """
        # 1. Try remote HEAD first (best for repos with remotes)
        output = await self._run_git_command(
            ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            raise_on_error=False,
            timeout=10.0,
        )
        if output:
            return output

        # 2. Check for common default branch names
        for branch_name in ["main", "master"]:
            exists = await self._run_git_command(
                ["rev-parse", "--verify", f"refs/heads/{branch_name}"],
                raise_on_error=False,
                timeout=10.0,
            )
            if exists:
                return branch_name

        # 3. Last resort: local HEAD (may not be the default branch)
        output = await self._run_git_command(
            ["symbolic-ref", "--short", "HEAD"],
            raise_on_error=False,
            timeout=10.0,
        )
        if output:
            return output

        raise Exception(
            "Unable to determine repository default branch. "
            "Ensure the repository has at least one commit and a valid HEAD."
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

    async def has_commits(self) -> bool:
        """Check if the repository has any commits.

        Returns:
            True if repository has at least one commit, False otherwise
        """
        output = await self._run_git_command(
            ["rev-parse", "HEAD"],
            raise_on_error=False,
            timeout=10.0,
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

    async def get_conflicted_files(self) -> list[str]:
        """Get list of files with unmerged conflicts.

        Returns:
            List of file paths that have unmerged conflicts
        """
        output = await self._run_git_command(["diff", "--name-only", "--diff-filter=U"])
        return [f for f in output.strip().split("\n") if f]

    async def switch_detach(self) -> None:
        """Detach HEAD from the current branch.

        This releases the branch so it can be checked out in another worktree.

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["switch", "--detach"])

    async def fetch(self, remote: str = "origin") -> None:
        """Fetch latest changes from a remote.

        Args:
            remote: Remote name to fetch from (default: origin)

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["fetch", remote])

    async def rebase_onto(self, onto: str, abort_on_conflict: bool = True) -> str:
        """Rebase the current branch onto another branch.

        This performs `git rebase <onto>` which rebases the current HEAD onto <onto>.
        Use this when working in a worktree where the branch is already checked out.

        Args:
            onto: Branch to rebase onto
            abort_on_conflict: If True (default), abort rebase on conflict. If False,
                leave rebase paused on conflict for manual resolution.

        Returns:
            New HEAD commit hash after successful rebase

        Raises:
            RebaseConflictError: If rebase encounters conflicts (rebase is aborted if abort_on_conflict=True)
            ShellCommandExecutionError: If git command fails for other reasons
        """
        try:
            await self._run_git_command(["rebase", onto])
        except ShellCommandExecutionError as e:
            # Check if this is a conflict error
            error_msg = str(e).lower()
            if "conflict" in error_msg or "could not apply" in error_msg:
                if abort_on_conflict:
                    # Abort the rebase
                    await self._run_git_command(["rebase", "--abort"], raise_on_error=False)
                raise RebaseConflictError(f"Rebase onto {onto} encountered conflicts") from e
            # Re-raise other errors
            raise

        # Return new HEAD commit hash
        return await self._run_git_command(["rev-parse", "HEAD"])

    async def rebase_branch(self, branch: str, onto: str, abort_on_conflict: bool = True) -> str:
        """Rebase a branch onto another branch.

        This performs `git rebase <onto> <branch>` which rebases <branch> onto <onto>.

        Args:
            branch: Branch to rebase
            onto: Branch to rebase onto
            abort_on_conflict: If True (default), abort rebase on conflict. If False,
                leave rebase paused on conflict for manual resolution.

        Returns:
            New HEAD commit hash after successful rebase

        Raises:
            RebaseConflictError: If rebase encounters conflicts (rebase is aborted if abort_on_conflict=True)
            ShellCommandExecutionError: If git command fails for other reasons
        """
        try:
            await self._run_git_command(["rebase", onto, branch])
        except ShellCommandExecutionError as e:
            # Check if this is a conflict error
            error_msg = str(e).lower()
            if "conflict" in error_msg or "could not apply" in error_msg:
                if abort_on_conflict:
                    # Abort the rebase
                    await self._run_git_command(["rebase", "--abort"], raise_on_error=False)
                raise RebaseConflictError(f"Rebase of {branch} onto {onto} encountered conflicts") from e
            # Re-raise other errors
            raise

        # Return new HEAD commit hash
        return await self._run_git_command(["rev-parse", "HEAD"])

    def is_rebase_in_progress(self) -> bool:
        """Check if a rebase is currently in progress.

        Checks for the existence of `.git/rebase-merge/` or `.git/rebase-apply/` directories.

        Returns:
            True if a rebase is in progress, False otherwise
        """
        git_dir = self._repo_path / ".git"

        # For worktrees, .git is a file pointing to the actual git dir
        if git_dir.is_file():
            # Read the gitdir path from the file
            content = git_dir.read_text().strip()
            if content.startswith("gitdir: "):
                git_dir = Path(content[8:])

        rebase_merge = git_dir / "rebase-merge"
        rebase_apply = git_dir / "rebase-apply"

        return rebase_merge.exists() or rebase_apply.exists()

    async def rebase_continue(self) -> str:
        """Continue a paused rebase after conflicts have been resolved.

        Automatically stages all changes before continuing, since during a rebase
        conflict state the only unstaged changes should be the resolved conflict files.

        Returns:
            New HEAD commit hash after successful rebase continuation

        Raises:
            RebaseConflictError: If rebase encounters more conflicts (files still have conflict markers)
            ShellCommandExecutionError: If git command fails for other reasons
        """
        # Stage all changes - during rebase conflict, unstaged changes are the resolved files
        await self._run_git_command(["add", "-A"])

        try:
            await self._run_git_command(["rebase", "--continue"])
        except ShellCommandExecutionError as e:
            # Check if this is a conflict error
            error_msg = str(e).lower()
            if "conflict" in error_msg or "could not apply" in error_msg:
                raise RebaseConflictError("Rebase continue encountered conflicts") from e
            # Re-raise other errors
            raise

        # Return new HEAD commit hash
        return await self._run_git_command(["rev-parse", "HEAD"])

    async def rebase_abort(self) -> None:
        """Abort an in-progress rebase.

        Executes `git rebase --abort` to cancel the rebase and restore
        the branch to its state before the rebase started.

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["rebase", "--abort"])

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

    async def stage_untracked_files_intent(self) -> list[str]:
        """Stage untracked files with intent-to-add (git add -N).

        This makes untracked files visible in `git diff` output without
        staging their content. Respects .gitignore automatically.

        Returns:
            List of file paths that were staged with intent-to-add
        """
        # Get untracked files via git status --porcelain
        output = await self._run_git_command(
            ["status", "--porcelain"],
            raise_on_error=False,
        )

        if not output:
            return []

        # Find untracked files (lines starting with ??)
        untracked_files = []
        for line in output.split("\n"):
            if line.startswith("?? "):
                # Extract file path (remove "?? " prefix)
                file_path = line[3:].strip()
                # Remove quotes if present (git quotes paths with special chars)
                if file_path.startswith('"') and file_path.endswith('"'):
                    file_path = file_path[1:-1]
                untracked_files.append(file_path)

        if not untracked_files:
            return []

        # Stage each untracked file with intent-to-add
        staged_files = []
        for file_path in untracked_files:
            try:
                await self._run_git_command(
                    ["add", "-N", file_path],
                    raise_on_error=False,
                )
                staged_files.append(file_path)
            except Exception as e:
                logfire.warning(f"Failed to stage untracked file with intent-to-add: {file_path}", error=str(e))

        if staged_files:
            logfire.info(f"Staged {len(staged_files)} untracked files with intent-to-add")

        return staged_files

    async def stash(self, message: str | None = None) -> str | None:
        """Stash uncommitted changes.

        Args:
            message: Optional message for the stash entry

        Returns:
            Stash reference (e.g., 'stash@{0}') if changes were stashed, None if nothing to stash
        """
        # Check if there are changes to stash first
        if not await self.has_uncommitted_changes():
            return None

        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        await self._run_git_command(args)

        # Return the stash reference
        return "stash@{0}"

    async def stash_pop(self) -> bool:
        """Restore stashed changes.

        Returns:
            True if stash was popped successfully, False if no stash to pop
        """
        # Check if there are any stashes
        stash_list = await self._run_git_command(["stash", "list"], raise_on_error=False)
        if not stash_list:
            return False

        await self._run_git_command(["stash", "pop"])
        return True

    async def stash_push(self, include_untracked: bool = False, message: str | None = None) -> str:
        """Stash changes, clear working tree, and return the stash SHA.

        Note: Caller should check has_uncommitted_changes() first if needed.
        If called with no changes, git stash push will succeed but create no stash.

        Args:
            include_untracked: If True, include untracked (new) files in stash
            message: Optional message for the stash entry

        Returns:
            SHA of the stash commit (stable identifier that works across worktrees)
        """
        # Stage all changes first to sync index with working tree
        # This prevents "not uptodate" errors when files have partial staging
        await self._run_git_command(["add", "-A"])

        args = ["stash", "push"]
        if include_untracked:
            args.append("-u")
        if message:
            args.extend(["-m", message])

        await self._run_git_command(args)
        # Return SHA instead of "stash@{0}" for stability across worktrees
        sha = await self._run_git_command(["rev-parse", "stash@{0}"])
        return sha.strip()

    async def stash_apply(self, stash_ref: str) -> None:
        """Apply a stash by reference or SHA.

        Args:
            stash_ref: The stash reference (e.g., 'stash@{0}') or commit SHA

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["stash", "apply", stash_ref])

    async def find_stash_by_message(self, message_pattern: str) -> str | None:
        """Find a stash entry by message pattern.

        Args:
            message_pattern: Substring to search for in stash messages

        Returns:
            Stash reference (e.g., 'stash@{0}') if found, None otherwise
        """
        stash_list = await self._run_git_command(["stash", "list"], raise_on_error=False)
        if not stash_list:
            return None

        for line in stash_list.split("\n"):
            if message_pattern in line:
                # Extract stash reference from the line (format: "stash@{N}: ...")
                if ":" in line:
                    stash_ref = line.split(":")[0].strip()
                    return stash_ref
        return None

    async def stash_drop(self, stash_ref: str) -> None:
        """Drop a stash entry.

        Args:
            stash_ref: The stash reference (e.g., 'stash@{0}')

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["stash", "drop", stash_ref])

    async def stash_store(self, commit_sha: str, message: str | None = None) -> None:
        """Store a stash commit to the stash list.

        This makes the stash accessible via 'git stash list' and 'git stash apply stash@{0}'.

        Args:
            commit_sha: The SHA of the stash commit to store
            message: Optional message for the stash entry

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        args = ["stash", "store", commit_sha]
        if message:
            args.extend(["-m", message])
        await self._run_git_command(args)

    async def reset_working_tree(self, include_untracked: bool = True) -> None:
        """Reset all uncommitted changes in the working tree.

        Args:
            include_untracked: If True, also remove untracked files

        Raises:
            ShellCommandExecutionError: If git command fails
        """
        await self._run_git_command(["checkout", "."])
        if include_untracked:
            await self._run_git_command(["clean", "-fd"])

    async def merge_squash(
        self,
        source: str,
        target: str,
        title: str | None = None,
    ) -> str:
        """Perform a squash merge.

        Merges all commits from source branch into target branch as a single commit.
        Checks out target branch, performs squash merge, and commits with auto-generated
        message from the squashed commits.

        Args:
            source: Source branch to squash merge from
            target: Target branch to merge into
            title: Optional title for the commit (prepended to auto-generated message)

        Returns:
            Commit hash of the new squashed commit

        Raises:
            ShellCommandExecutionError: If merge or commit fails
        """
        # Get commit messages from source branch for auto-generated message
        merge_base = await self.get_merge_base(target, source)
        commits = await self.get_commits_in_range(merge_base, source)

        # Build commit message
        if title:
            message_lines = [title, ""]
        else:
            message_lines = [f"Squash merge branch '{source}' into {target}", ""]

        # Add individual commit messages
        if commits:
            message_lines.append("Squashed commits:")
            for commit in commits:
                # Indent each commit message
                message_lines.append(f"* {commit.message}")

        message = "\n".join(message_lines)

        # Checkout target branch
        await self.checkout_branch(target)

        # Perform the squash merge (stages changes but doesn't commit)
        await self._run_git_command(["merge", "--squash", source])

        # Commit the squashed changes
        await self._run_git_command(["commit", "-m", message])

        # Return the new commit hash
        return await self._run_git_command(["rev-parse", "HEAD"])

    async def push_branch(self, branch: str, remote: str = "origin", set_upstream: bool = True) -> None:
        """Push a branch to a remote.

        Args:
            branch: Branch name to push
            remote: Remote name (default: origin)
            set_upstream: Whether to set upstream tracking (default: True)

        Raises:
            ShellCommandExecutionError: If push fails
        """
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.extend([remote, branch])
        await self._run_git_command(args, timeout=60.0)

    async def push_delete_branch(self, branch: str, remote: str = "origin") -> None:
        """Delete a branch from a remote.

        Args:
            branch: Branch name to delete
            remote: Remote name (default: origin)

        Raises:
            ShellCommandExecutionError: If deletion fails
        """
        await self._run_git_command(["push", remote, "--delete", branch], timeout=60.0)

    async def get_checked_out_location(self, branch: str) -> str | None:
        """Get the path where a branch is currently checked out.

        Checks the main repository and all worktrees to find where the branch
        is currently checked out.

        Args:
            branch: Branch name to look for

        Returns:
            Path where the branch is checked out, or None if not checked out anywhere
        """
        worktrees = await self.list_worktrees()
        for worktree in worktrees:
            if worktree.branch == branch:
                return worktree.path
        return None

    async def release_branch_from_worktree(
        self,
        branch_name: str,
        exclude_main_repo: bool = True,
    ) -> BranchReleaseResult:
        """Find where a branch is checked out and release it by detaching HEAD.

        This allows operations like delete or rebase on branches that are
        currently checked out in a worktree.

        Args:
            branch_name: Branch to release
            exclude_main_repo: If True, don't release if checked out in main repo

        Returns:
            BranchReleaseResult with worktree_path and stash_sha if released
        """
        checkout_path = await self.get_checked_out_location(branch_name)

        if not checkout_path:
            return BranchReleaseResult(None, None)

        if exclude_main_repo and checkout_path == str(self._repo_path):
            return BranchReleaseResult(None, None)

        worktree_git = GitRepoIntegration(checkout_path)
        stash_sha: str | None = None

        if await worktree_git.has_uncommitted_changes():
            stash_sha = await worktree_git.stash_push(include_untracked=True)
            logfire.info(f"Stashed uncommitted changes before releasing {branch_name}")

        await worktree_git.switch_detach()
        logfire.info(f"Detached HEAD, released branch {branch_name} from {checkout_path}")

        return BranchReleaseResult(checkout_path, stash_sha)

    async def is_branch_pushed(self, branch: str, remote: str = "origin") -> bool:
        """Check if a local branch has been pushed to a remote.

        Args:
            branch: Local branch name
            remote: Remote name (default: origin)

        Returns:
            True if the branch exists on the remote, False otherwise
        """
        output = await self._run_git_command(
            ["ls-remote", "--heads", remote, branch],
            raise_on_error=False,
            timeout=30.0,
        )
        return bool(output)

    async def fast_forward_merge(self, source: str, target: str) -> str:
        """Perform a fast-forward merge.

        Checks out the target branch and fast-forwards it to the source branch.
        Fast-forward is only possible when target is an ancestor of source
        (i.e., target hasn't diverged).

        Args:
            source: Source branch to fast-forward to
            target: Target branch to update

        Returns:
            Commit hash after fast-forward

        Raises:
            ShellCommandExecutionError: If fast-forward is not possible
        """
        await self.checkout_branch(target)
        await self._run_git_command(["merge", "--ff-only", source])
        return await self._run_git_command(["rev-parse", "HEAD"])

    async def commit(self, message: str) -> str:
        """Create a commit with staged changes.

        Args:
            message: Commit message

        Returns:
            Hash of the new commit

        Raises:
            ShellCommandExecutionError: If commit fails
        """
        await self._run_git_command(["commit", "-m", message])
        return await self._run_git_command(["rev-parse", "HEAD"])
