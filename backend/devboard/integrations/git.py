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

GITIGNORE_CONTENT = """\
# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
"""

# Environment variables to prevent git from prompting for input
GIT_ENV = {
    "GIT_EDITOR": "true",  # Prevents editor prompts (e.g., during rebase --continue)
    "GIT_TERMINAL_PROMPT": "0",  # Prevents credential prompts
}


def parse_remote_branch(base_branch: str, remotes: list[str]) -> tuple[str, str] | None:
    """Parse a remote-tracking branch ref into (remote, branch_name).

    Returns None if base_branch is a local branch (no matching remote prefix).
    Example: parse_remote_branch("origin/main", ["origin"]) -> ("origin", "main")
    """
    for remote in remotes:
        if base_branch.startswith(remote + "/"):
            return remote, base_branch[len(remote) + 1 :]
    return None


class GitRepoIntegration:
    """
    Integration for Git operations on code repositories.
    Provides branch management, worktree operations, and repository analysis.
    """

    def __init__(self, repo_path: str | Path):
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

    @property
    def repo_path(self) -> Path:
        return self._repo_path

    async def run_git_command(
        self,
        args: list[str],
        raise_on_error: bool = True,
        timeout: float = 30.0,
    ) -> str:
        """Run a git command in the repo dir. args should not include the leading 'git'."""
        result = await execute_shell_command(
            ["git"] + args,
            working_dir=self._repo_path,
            timeout=timeout,
            raise_on_error=raise_on_error,
            env=GIT_ENV,
        )
        return result.stdout.strip() if result.success else ""

    async def get_git_log(self, max_count: int = 10, file_path: str | None = None) -> list[GitLogEntry]:
        # Use null bytes as field delimiters and RS (record separator, \x1e) as record separator
        # Format: hash\x00author\x00date\x00subject\x00body\x1e
        args = [
            "log",
            f"--max-count={max_count}",
            "--pretty=format:%H%x00%an%x00%ad%x00%s%x00%b%x1e",
            "--date=iso",
        ]
        if file_path:
            args.append("--")
            args.append(file_path)

        output = await self.run_git_command(args)

        return self._parse_git_log_output(output)

    async def get_git_diff(
        self,
        commit1: str | None = None,
        commit2: str | None = None,
        file_path: str | None = None,
    ) -> str:
        args = ["diff"]
        if commit1:
            if commit2:
                args.append(f"{commit1}..{commit2}")
            else:
                args.append(commit1)

        if file_path:
            args.append("--")
            args.append(file_path)

        return await self.run_git_command(args)

    async def get_merge_base(self, branch1: str, branch2: str) -> str:
        return await self.run_git_command(["merge-base", branch1, branch2])

    async def get_fork_point(self, base_branch: str, feature_branch: str) -> str | None:
        """Return the merge-base commit where feature_branch diverged from base_branch, or None if undeterminable."""
        merge_base = await self.run_git_command(
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

    def _parse_git_log_output(self, output: str) -> list[GitLogEntry]:
        """Parse git log output. Expected format per record: hash\x00author\x00date\x00subject\x00body\x1e"""
        commits: list[GitLogEntry] = []
        if not output.strip():
            return commits

        # Split by RS (record separator, \x1e)
        records = output.split("\x1e")

        for record in records:
            record = record.strip()
            if not record:
                continue

            # Split by null byte (field separator)
            parts = record.split("\x00", 4)
            if len(parts) >= 4:
                body = parts[4].strip() if len(parts) > 4 and parts[4].strip() else None
                commits.append(
                    GitLogEntry(
                        hash=parts[0],
                        author=parts[1],
                        date=parts[2],
                        subject=parts[3],
                        body=body,
                    )
                )

        return commits

    async def get_commits_in_range(
        self,
        base_commit: str,
        head_commit: str,
        file_paths: list[str] | None = None,
    ) -> list[GitLogEntry]:
        # Use null bytes as field delimiters and RS (\x1e) as record separator
        args = [
            "log",
            f"{base_commit}..{head_commit}",
            "--pretty=format:%H%x00%an%x00%ad%x00%s%x00%b%x1e",
            "--date=iso",
        ]

        # Add file path filter if provided
        if file_paths:
            args.append("--")
            args.extend(file_paths)

        output = await self.run_git_command(args)

        return self._parse_git_log_output(output)

    async def get_commit_diff(self, commit_hash: str) -> str:
        return await self.run_git_command(["show", "--format=", commit_hash])

    def _parse_git_diff(self, raw_diff: str) -> StructuredDiff:
        """Parse raw git diff output into a StructuredDiff."""
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
        raw_diff = await self.get_git_diff(commit1=commit1, commit2=commit2)
        return self._parse_git_diff(raw_diff)

    async def get_structured_commit_diff(self, commit_hash: str) -> CommitDiff:
        # Get commit metadata using show with format
        output = await self.run_git_command(
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
        args = ["branch"]
        if remote:
            args.append("-r")

        output = await self.run_git_command(args)
        branches: list[str] = []
        for line in output.split("\n"):
            branch = line.strip()
            if branch and not branch.startswith("*"):
                branches.append(branch)
            elif branch.startswith("* "):
                branches.append(branch[2:])

        return branches

    async def list_worktrees(self) -> list[WorktreeInfo]:
        output = await self.run_git_command(["worktree", "list", "--porcelain"])

        worktrees: list[WorktreeInfo] = []
        current_worktree: dict[str, str] = {}

        for line in output.split("\n"):
            line = line.strip()
            if not line:
                if current_worktree:
                    # Determine if this is the main repository
                    is_main: bool = current_worktree.get("path") == str(self._repo_path)
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
        await self.run_git_command(["worktree", "add", path, branch])

    async def remove_worktree(self, path: str, force: bool = False) -> None:
        args = ["worktree", "remove", path]
        if force:
            args.append("--force")
        await self.run_git_command(args)

    async def prune_worktrees(self) -> None:
        """Remove stale git worktree references for directories that no longer exist on disk."""
        await self.run_git_command(["worktree", "prune"])

    async def create_branch(self, name: str, base: str = "HEAD") -> None:
        """Create a branch from base without checking it out."""
        await self.run_git_command(["branch", name, base])

    async def checkout_branch(self, name: str) -> None:
        await self.run_git_command(["checkout", name])

    async def delete_branch(self, name: str, force: bool = False) -> None:
        args = ["branch"]
        args.append("-D" if force else "-d")
        args.append(name)
        await self.run_git_command(args)

    async def get_current_branch(self) -> str:
        return await self.run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])

    async def get_in_progress_operation_branch(self) -> str | None:
        """Return the branch name being rebased, or None if no rebase is in progress.

        During a rebase HEAD is detached, so get_current_branch() returns 'HEAD'. This method reads rebase state files to recover the original branch name.
        """
        git_dir_str = await self.run_git_command(["rev-parse", "--git-dir"])
        git_dir = self._repo_path / git_dir_str

        for candidate in ["rebase-merge/head-name", "rebase-apply/head-name"]:
            head_name_file = git_dir / candidate
            if head_name_file.exists():
                ref = head_name_file.read_text().strip()
                if ref.startswith("refs/heads/"):
                    return ref[len("refs/heads/") :]
                return ref

        return None

    async def get_branch_head(self, branch: str) -> str | None:
        """Return the HEAD commit hash of branch, or None if the branch doesn't exist. Accepts local or remote branch names (e.g. 'main', 'origin/main')."""
        result = await self.run_git_command(
            ["rev-parse", "--verify", branch],
            raise_on_error=False,
        )
        return result if result else None

    async def get_default_branch(self) -> str:
        """Detect the repository default branch.

        Detection order: remote HEAD ref → common local names (main, master) → local HEAD.
        Returns a remote-tracking ref (e.g. 'origin/main') when a remote is configured.
        """
        for remote in await self.list_remotes():
            output = await self.run_git_command(
                ["symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD"],
                raise_on_error=False,
                timeout=10.0,
            )
            if output:
                return output

        for branch_name in ["main", "master"]:
            exists = await self.run_git_command(
                ["rev-parse", "--verify", f"refs/heads/{branch_name}"],
                raise_on_error=False,
                timeout=10.0,
            )
            if exists:
                return branch_name

        # 3. Last resort: local HEAD (may not be the default branch)
        output = await self.run_git_command(
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
        output = await self.run_git_command(
            ["rev-parse", "--verify", f"refs/heads/{name}"],
            raise_on_error=False,
        )
        return bool(output)

    async def has_commits(self) -> bool:
        output = await self.run_git_command(
            ["rev-parse", "HEAD"],
            raise_on_error=False,
            timeout=10.0,
        )
        return bool(output)

    async def get_branch_comparison(self, branch: str, base: str) -> BranchComparison:
        # Get ahead/behind counts
        ahead = 0
        behind = 0
        try:
            output = await self.run_git_command(["rev-list", "--left-right", "--count", f"{base}...{branch}"])
            parts = output.split()
            behind = int(parts[0]) if len(parts) > 0 else 0
            ahead = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            logfire.warning(f"Failed to parse branch comparison counts for {branch} vs {base}")

        # Check for merge conflicts using merge-tree
        has_conflicts = False
        try:
            # Get merge base
            merge_base = await self.run_git_command(["merge-base", base, branch])
            # Check for conflicts with merge-tree
            merge_tree_output = await self.run_git_command(["merge-tree", merge_base, base, branch])
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
        """Checkout target and merge source into it. Returns the new HEAD hash."""
        # First checkout the target branch
        await self.checkout_branch(target)

        # Perform the merge
        args = ["merge", source]
        if no_ff:
            args.append("--no-ff")
        await self.run_git_command(args)

        # Return the new HEAD commit hash
        return await self.run_git_command(["rev-parse", "HEAD"])

    async def has_uncommitted_changes(self, include_untracked: bool = False) -> bool:
        """Return True if the working directory has staged or unstaged changes.

        include_untracked=False (default) ignores untracked files — use this when checking whether a merge/rebase operation is blocked.
        """
        args = ["status", "--porcelain"] + ([] if include_untracked else ["-uno"])
        output = await self.run_git_command(args, raise_on_error=False)
        return bool(output)

    async def get_uncommitted_change_count(self, include_untracked: bool = False) -> int:
        args = ["status", "--porcelain"] + ([] if include_untracked else ["-uno"])
        output = await self.run_git_command(args, raise_on_error=False)
        if not output:
            return 0
        return len([line for line in output.splitlines() if line.strip()])

    async def get_uncommitted_file_paths(self) -> list[str]:
        """Return deduplicated file paths with staged or unstaged changes."""
        unstaged = await self.run_git_command(["diff", "--name-only"], raise_on_error=False)
        staged = await self.run_git_command(["diff", "--name-only", "--cached"], raise_on_error=False)
        paths: set[str] = set()
        for output in (unstaged, staged):
            paths.update(f for f in output.strip().split("\n") if f)
        return sorted(paths)

    async def get_changed_file_paths(self, commit_a: str, commit_b: str, from_merge_base: bool = False) -> list[str]:
        """Return file paths changed between commit_a and commit_b.

        When from_merge_base=True, uses three-dot diff (commit_b changes since divergence from commit_a) instead of direct two-tip comparison.
        """
        ref_args = [f"{commit_a}...{commit_b}"] if from_merge_base else [commit_a, commit_b]
        output = await self.run_git_command(["diff", "--name-only", *ref_args], raise_on_error=False)
        return [f for f in output.strip().split("\n") if f]

    async def get_conflicted_files(self) -> list[str]:
        output = await self.run_git_command(["diff", "--name-only", "--diff-filter=U"])
        return [f for f in output.strip().split("\n") if f]

    async def switch_detach(self) -> None:
        """Detach HEAD, releasing the current branch so it can be checked out in another worktree."""
        await self.run_git_command(["switch", "--detach"])

    async def list_remotes(self) -> list[str]:
        """Return all configured remote names for this repository."""
        output = await self.run_git_command(["remote"], raise_on_error=False, timeout=10.0)
        return output.splitlines() if output else []

    async def fetch(self, remote: str = "origin", branch: str | None = None, timeout: float = 30.0) -> None:
        args = ["fetch", remote]
        if branch:
            args.append(branch)
        await self.run_git_command(args, timeout=timeout)

    async def rebase_branch(self, branch: str, onto: str, abort_on_conflict: bool = True) -> str:
        """Rebase branch onto onto (git rebase <onto> <branch>).

        Raises RebaseConflictError on conflicts; aborts the rebase first if abort_on_conflict=True (default).
        """
        try:
            await self.run_git_command(["rebase", onto, branch])
        except ShellCommandExecutionError as e:
            # Check if this is a conflict error
            error_msg = str(e).lower()
            if "conflict" in error_msg or "could not apply" in error_msg:
                if abort_on_conflict:
                    # Abort the rebase
                    await self.run_git_command(["rebase", "--abort"], raise_on_error=False)
                raise RebaseConflictError(f"Rebase of {branch} onto {onto} encountered conflicts") from e
            # Re-raise other errors
            raise

        # Return new HEAD commit hash
        return await self.run_git_command(["rev-parse", "HEAD"])

    def is_rebase_in_progress(self) -> bool:
        """Return True if a rebase is in progress (rebase-merge/ or rebase-apply/ directory exists)."""
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
        """Stage all changes and continue a paused rebase. Raises RebaseConflictError if conflicts remain."""
        # Stage all changes - during rebase conflict, unstaged changes are the resolved files
        await self.run_git_command(["add", "-A"])

        try:
            await self.run_git_command(["rebase", "--continue"])
        except ShellCommandExecutionError as e:
            # Check if this is a conflict error
            error_msg = str(e).lower()
            if "conflict" in error_msg or "could not apply" in error_msg:
                raise RebaseConflictError("Rebase continue encountered conflicts") from e
            # Re-raise other errors
            raise

        # Return new HEAD commit hash
        return await self.run_git_command(["rev-parse", "HEAD"])

    async def rebase_abort(self) -> None:
        await self.run_git_command(["rebase", "--abort"])

    async def detect_git_remote_url(self) -> str | None:
        # Try to get "origin" remote URL
        output = await self.run_git_command(
            ["remote", "get-url", "origin"],
            raise_on_error=False,
            timeout=10.0,
        )

        if output:
            return output

        # If no origin, list all remotes and get URL of first remote
        remotes = await self.run_git_command(
            ["remote"],
            raise_on_error=False,
            timeout=10.0,
        )

        if remotes:
            first_remote = remotes.split("\n")[0]
            output = await self.run_git_command(
                ["remote", "get-url", first_remote],
                raise_on_error=False,
                timeout=10.0,
            )

            if output:
                return output

        return None

    async def stage_untracked_files_intent(self) -> list[str]:
        """Stage untracked files with intent-to-add (git add -N) so they appear in git diff without staging content."""
        # Get untracked files via git status --porcelain
        output = await self.run_git_command(
            ["status", "--porcelain"],
            raise_on_error=False,
        )

        if not output:
            return []

        # Find untracked files (lines starting with ??)
        untracked_files: list[str] = []
        for line in output.split("\n"):
            if line.startswith("?? "):
                # Extract file path (remove "?? " prefix)
                file_path: str = line[3:].strip()
                # Remove quotes if present (git quotes paths with special chars)
                if file_path.startswith('"') and file_path.endswith('"'):
                    file_path = file_path[1:-1]
                untracked_files.append(file_path)

        if not untracked_files:
            return []

        # Stage each untracked file with intent-to-add
        staged_files: list[str] = []
        for file_path in untracked_files:
            try:
                await self.run_git_command(
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
        """Stash uncommitted changes. Returns the stash ref, or None if the working tree was clean."""
        # Check if there are changes to stash first
        if not await self.has_uncommitted_changes():
            return None

        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        await self.run_git_command(args)

        # Return the stash reference
        return "stash@{0}"

    async def stash_pop(self) -> bool:
        # Check if there are any stashes
        stash_list = await self.run_git_command(["stash", "list"], raise_on_error=False)
        if not stash_list:
            return False

        await self.run_git_command(["stash", "pop"])
        return True

    async def stash_push(self, include_untracked: bool = False, message: str | None = None) -> str | None:
        """Stash all changes (staged + unstaged + optionally untracked) and return the stash commit SHA.

        Returns None if there was nothing to stash. Returns a SHA (not 'stash@{0}') for stability when used across worktrees.
        """
        # Stage all changes first to sync index with working tree
        # This prevents "not uptodate" errors when files have partial staging
        await self.run_git_command(["add", "-A"])

        args = ["stash", "push"]
        if include_untracked:
            args.append("-u")
        if message:
            args.extend(["-m", message])

        output = await self.run_git_command(args)
        if "No local changes to save" in output:
            return None

        # Return SHA instead of "stash@{0}" for stability across worktrees
        sha = await self.run_git_command(["rev-parse", "stash@{0}"])
        return sha.strip()

    async def stash_apply(self, stash_ref: str) -> None:
        await self.run_git_command(["stash", "apply", stash_ref])

    async def find_stash_by_message(self, message_pattern: str) -> str | None:
        stash_list = await self.run_git_command(["stash", "list"], raise_on_error=False)
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
        await self.run_git_command(["stash", "drop", stash_ref])

    async def stash_store(self, commit_sha: str, message: str | None = None) -> None:
        """Store a stash commit (by SHA) into the stash list, making it accessible via 'git stash list'."""
        args = ["stash", "store", commit_sha]
        if message:
            args.extend(["-m", message])
        await self.run_git_command(args)

    async def reset_working_tree(self, include_untracked: bool = True) -> None:
        await self.run_git_command(["checkout", "."])
        if include_untracked:
            await self.run_git_command(["clean", "-fd"])

    async def merge_squash(
        self,
        source: str,
        target: str,
        title: str | None = None,
    ) -> str:
        """Checkout target, squash-merge source, and commit. Returns the new HEAD hash."""
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
                message_lines.append(f"* {commit.subject}")

        message = "\n".join(message_lines)

        # Checkout target branch
        await self.checkout_branch(target)

        # Perform the squash merge (stages changes but doesn't commit)
        await self.run_git_command(["merge", "--squash", source])

        # Commit the squashed changes
        await self.run_git_command(["commit", "-m", message])

        # Return the new commit hash
        return await self.run_git_command(["rev-parse", "HEAD"])

    async def push_branch(self, branch: str, remote: str = "origin", set_upstream: bool = True) -> None:
        args = ["push"]
        if set_upstream:
            args.append("-u")
        args.extend([remote, branch])
        await self.run_git_command(args, timeout=60.0)

    async def push_delete_branch(self, branch: str, remote: str = "origin") -> None:
        await self.run_git_command(["push", remote, "--delete", branch], timeout=60.0)

    async def get_checked_out_location(self, branch: str) -> str | None:
        """Return the path where branch is currently checked out (main repo or any worktree), or None."""
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
        """Detach HEAD in the worktree where branch_name is checked out, releasing it for operations like delete/rebase.

        Stashes any uncommitted changes before detaching. Does nothing if the branch is not checked out, or if it is only checked out in the main repo and exclude_main_repo=True.
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
        output = await self.run_git_command(
            ["ls-remote", "--heads", remote, branch],
            raise_on_error=False,
            timeout=30.0,
        )
        return bool(output)

    async def fast_forward_merge(self, source: str, target: str) -> str:
        """Checkout target and fast-forward it to source. Returns the new HEAD hash."""
        await self.checkout_branch(target)
        await self.run_git_command(["merge", "--ff-only", source])
        return await self.run_git_command(["rev-parse", "HEAD"])

    async def commit(self, message: str, no_verify: bool = False) -> str:
        """Commit staged changes. no_verify=True skips hooks (safe for squashing already-verified commits)."""
        args = ["commit", "-m", message]
        if no_verify:
            args.append("--no-verify")
        await self.run_git_command(args)
        return await self.run_git_command(["rev-parse", "HEAD"])

    async def soft_reset(self, commit: str) -> None:
        """Reset HEAD to commit, keeping all changes staged (git reset --soft)."""
        await self.run_git_command(["reset", "--soft", commit])

    async def rebase_onto(self, onto: str) -> str:
        """Rebase the current branch onto onto in-place.

        Unlike rebase_branch, operates on the checked-out branch directly, making it safe to call from within a worktree. Raises RebaseConflictError on conflicts (and aborts).
        """
        try:
            await self.run_git_command(["rebase", onto])
        except ShellCommandExecutionError as e:
            error_msg = str(e).lower()
            if "conflict" in error_msg or "could not apply" in error_msg:
                await self.run_git_command(["rebase", "--abort"], raise_on_error=False)
                raise RebaseConflictError(f"Rebase onto {onto} encountered conflicts") from e
            raise
        return await self.run_git_command(["rev-parse", "HEAD"])

    @classmethod
    async def clone_repo(cls, url: str, target_path: str | Path) -> "GitRepoIntegration":
        """Clone a remote repository to target_path and return a GitRepoIntegration instance.

        Raises ShellCommandExecutionError on failure (e.g., invalid URL, network error, target exists).
        """
        target_path = Path(target_path)
        await execute_shell_command(
            ["git", "clone", url, str(target_path)],
            timeout=300.0,
            raise_on_error=True,
            env=GIT_ENV,
        )
        logfire.info("Cloned repository", url=url, target_path=str(target_path))
        return cls(target_path)

    @classmethod
    async def init_repo(cls, path: str | Path) -> "GitRepoIntegration":
        """Initialize a new git repository at path (creating the directory if needed).

        Raises ShellCommandExecutionError on failure.
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        await execute_shell_command(
            ["git", "init"],
            working_dir=path,
            timeout=30.0,
            raise_on_error=True,
            env=GIT_ENV,
        )

        instance = cls(path)
        # Configure local user identity so commits work without a global git config
        await instance.run_git_command(["config", "user.email", "devboard@local"])
        await instance.run_git_command(["config", "user.name", "DevBoard"])
        logfire.info("Initialized git repository", path=str(path))
        return instance

    async def add_and_commit(self, message: str) -> None:
        """Stage all changes and commit with the given message.

        Raises ShellCommandExecutionError on failure.
        """
        await self.run_git_command(["add", "-A"])
        await self.run_git_command(["commit", "-m", message])
        logfire.info("Committed changes", path=str(self._repo_path), message=message)

    def write_initial_project_files(self, name: str, description: str | None) -> None:
        """Write .gitignore and README.md for a newly initialised project."""
        (self._repo_path / ".gitignore").write_text(GITIGNORE_CONTENT)
        readme_lines = [f"# {name}"]
        if description:
            readme_lines.append("")
            readme_lines.append(description)
        readme_lines.append("")
        (self._repo_path / "README.md").write_text("\n".join(readme_lines))
