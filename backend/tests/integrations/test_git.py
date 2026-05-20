"""Tests for Git integration methods."""

from unittest.mock import AsyncMock, patch

import pytest

from devboard.integrations.git import GitRepoIntegration, parse_remote_branch
from devboard.integrations.shell import ShellCommandExecutionError, ShellCommandResult
from devboard.integrations.types import BranchReleaseResult


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary directory with .git folder."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    return repo_path


class TestParseGitDiff:
    """Tests for _parse_git_diff method."""

    def test_parse_empty_diff(self, temp_git_repo):
        """Test parsing empty diff returns empty StructuredDiff."""
        git = GitRepoIntegration(temp_git_repo)
        result = git._parse_git_diff("")

        assert result.files == []
        assert result.additions == 0
        assert result.deletions == 0

    def test_parse_whitespace_only_diff(self, temp_git_repo):
        """Test parsing whitespace-only diff returns empty StructuredDiff."""
        git = GitRepoIntegration(temp_git_repo)
        result = git._parse_git_diff("   \n\t\n  ")

        assert result.files == []
        assert result.additions == 0
        assert result.deletions == 0

    def test_parse_simple_modified_file(self, temp_git_repo):
        """Test parsing diff for a simple modified file."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
-    print('hello')
+    print('hello world')
+    return True
"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 1
        assert result.files[0].file_path == "test.py"
        assert result.files[0].additions == 2
        assert result.files[0].deletions == 1
        assert result.files[0].is_new_file is False
        assert result.files[0].is_deleted is False
        assert result.additions == 2
        assert result.deletions == 1

    def test_parse_new_file_diff(self, temp_git_repo):
        """Test parsing diff for a new file detects is_new_file flag."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/newfile.py b/newfile.py
new file mode 100644
index 0000000..abcdefg
--- /dev/null
+++ b/newfile.py
@@ -0,0 +1,3 @@
+def new_function():
+    pass
+    return None
"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 1
        assert result.files[0].file_path == "newfile.py"
        assert result.files[0].is_new_file is True
        assert result.files[0].is_deleted is False
        assert result.files[0].additions == 3
        assert result.files[0].deletions == 0
        # Check that "new file mode 100644" is filtered out of diff_content
        assert "new file mode 100644" not in result.files[0].diff_content

    def test_parse_deleted_file_diff(self, temp_git_repo):
        """Test parsing diff for a deleted file detects is_deleted flag."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/oldfile.py b/oldfile.py
deleted file mode 100644
index abcdefg..0000000
--- a/oldfile.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def old_function():
-    pass
"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 1
        assert result.files[0].file_path == "oldfile.py"
        assert result.files[0].is_new_file is False
        assert result.files[0].is_deleted is True
        assert result.files[0].additions == 0
        assert result.files[0].deletions == 2
        # Check that "deleted file mode 100644" is filtered out of diff_content
        assert "deleted file mode 100644" not in result.files[0].diff_content

    def test_parse_multiple_files_diff(self, temp_git_repo):
        """Test parsing diff with multiple files."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/file1.py b/file1.py
index 1234567..abcdefg 100644
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,3 @@
 def func1():
+    # added comment
     pass
diff --git a/file2.py b/file2.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/file2.py
@@ -0,0 +1,2 @@
+def func2():
+    pass
diff --git a/file3.py b/file3.py
deleted file mode 100644
index abcdefg..0000000
--- a/file3.py
+++ /dev/null
@@ -1,1 +0,0 @@
-old_content
"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 3

        # file1.py - modified
        assert result.files[0].file_path == "file1.py"
        assert result.files[0].is_new_file is False
        assert result.files[0].is_deleted is False
        assert result.files[0].additions == 1

        # file2.py - new
        assert result.files[1].file_path == "file2.py"
        assert result.files[1].is_new_file is True
        assert result.files[1].is_deleted is False
        assert result.files[1].additions == 2

        # file3.py - deleted
        assert result.files[2].file_path == "file3.py"
        assert result.files[2].is_new_file is False
        assert result.files[2].is_deleted is True
        assert result.files[2].deletions == 1

        # Total stats
        assert result.additions == 3  # 1 + 2 + 0 (file3 is deleted, has 0 additions)
        assert result.deletions == 1

    def test_parse_filters_metadata_lines(self, temp_git_repo):
        """Test that various git metadata lines are filtered from diff_content."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/renamed.py b/renamed.py
similarity index 95%
rename from old_name.py
rename to renamed.py
old mode 100755
new mode 100644
index 1234567..abcdefg
--- a/old_name.py
+++ b/renamed.py
@@ -1,2 +1,2 @@
 def func():
-    old_line
+    new_line
"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 1
        file_diff = result.files[0]
        diff_content = file_diff.diff_content

        # These metadata lines should be filtered out
        assert "similarity index" not in diff_content
        assert "rename from" not in diff_content
        assert "rename to" not in diff_content
        assert "old mode" not in diff_content
        assert "new mode" not in diff_content

        # But diff headers and content should remain
        assert "diff --git" in diff_content
        assert "@@" in diff_content
        assert "+    new_line" in diff_content
        assert "-    old_line" in diff_content

        # Check that metadata fields are properly populated
        assert file_diff.old_file_path == "old_name.py"
        assert file_diff.is_mode_change is True
        assert file_diff.is_binary is False

    def test_parse_binary_file(self, temp_git_repo):
        """Test parsing diff for a binary file change."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/image.png b/image.png
index 1234567..abcdefg 100644
Binary files a/image.png and b/image.png differ"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 1
        file_diff = result.files[0]
        assert file_diff.file_path == "image.png"
        assert file_diff.is_binary is True
        assert "Binary files" in file_diff.diff_content

    def test_parse_pure_rename(self, temp_git_repo):
        """Test parsing diff for a pure rename (no content changes)."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 1
        file_diff = result.files[0]
        assert file_diff.file_path == "new_name.py"
        assert file_diff.old_file_path == "old_name.py"
        assert file_diff.additions == 0
        assert file_diff.deletions == 0
        # Pure rename should have no hunks in diff_content
        assert "@@" not in file_diff.diff_content

    def test_parse_mode_only_change(self, temp_git_repo):
        """Test parsing diff for a mode-only change (e.g., making script executable)."""
        git = GitRepoIntegration(temp_git_repo)
        raw_diff = """diff --git a/script.sh b/script.sh
old mode 100644
new mode 100755
"""
        result = git._parse_git_diff(raw_diff)

        assert len(result.files) == 1
        file_diff = result.files[0]
        assert file_diff.file_path == "script.sh"
        assert file_diff.is_mode_change is True
        assert file_diff.additions == 0
        assert file_diff.deletions == 0
        # Mode-only change should have no hunks
        assert "@@" not in file_diff.diff_content


class TestStageUntrackedFilesIntent:
    """Tests for stage_untracked_files_intent method."""

    @pytest.mark.asyncio
    async def test_stage_untracked_files_empty(self, temp_git_repo):
        """Test with no untracked files returns empty list."""
        git = GitRepoIntegration(temp_git_repo)

        mock_result = ShellCommandResult("", "", 0)

        with patch("devboard.integrations.git.execute_shell_command", return_value=mock_result):
            result = await git.stage_untracked_files_intent()

        assert result == []

    @pytest.mark.asyncio
    async def test_stage_untracked_files_success(self, temp_git_repo):
        """Test staging untracked files with intent-to-add."""
        git = GitRepoIntegration(temp_git_repo)

        # Mock git status output with untracked files
        status_output = """?? newfile1.py
?? newfile2.py
 M modified.py
"""

        async def mock_run_git_command(args, **kwargs):
            if args == ["status", "--porcelain"]:
                return status_output
            elif args[0] == "add" and args[1] == "-N":
                return ""
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.stage_untracked_files_intent()

        # Should return the two untracked files
        assert len(result) == 2
        assert "newfile1.py" in result
        assert "newfile2.py" in result
        # modified.py should not be included (it's modified, not untracked)
        assert "modified.py" not in result

    @pytest.mark.asyncio
    async def test_stage_untracked_files_handles_quoted_paths(self, temp_git_repo):
        """Test handling of quoted file paths with special characters."""
        git = GitRepoIntegration(temp_git_repo)

        # Git quotes paths with special characters
        status_output = """?? "file with spaces.py"
?? normal_file.py
"""

        async def mock_run_git_command(args, **kwargs):
            if args == ["status", "--porcelain"]:
                return status_output
            elif args[0] == "add" and args[1] == "-N":
                return ""
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.stage_untracked_files_intent()

        assert len(result) == 2
        assert "file with spaces.py" in result
        assert "normal_file.py" in result

    @pytest.mark.asyncio
    async def test_stage_untracked_files_only_processes_untracked(self, temp_git_repo):
        """Test that only untracked files (starting with ??) are processed."""
        git = GitRepoIntegration(temp_git_repo)

        # Various git status indicators
        status_output = """?? untracked.py
 M modified.py
A  added.py
D  deleted.py
MM both_modified.py
"""

        add_calls = []

        async def mock_run_git_command(args, **kwargs):
            if args == ["status", "--porcelain"]:
                return status_output
            elif args[0] == "add" and args[1] == "-N":
                add_calls.append(args[2])
                return ""
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.stage_untracked_files_intent()

        # Only untracked.py should be processed
        assert len(result) == 1
        assert result[0] == "untracked.py"
        assert add_calls == ["untracked.py"]

    @pytest.mark.asyncio
    async def test_stage_untracked_files_handles_add_failure(self, temp_git_repo):
        """Test that failures during git add -N are handled gracefully."""
        git = GitRepoIntegration(temp_git_repo)

        status_output = """?? file1.py
?? file2.py
"""
        call_count = 0

        async def mock_run_git_command(args, **kwargs):
            nonlocal call_count
            if args == ["status", "--porcelain"]:
                return status_output
            elif args[0] == "add" and args[1] == "-N":
                call_count += 1
                if args[2] == "file1.py":
                    raise Exception("Failed to add file1.py")
                return ""
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.stage_untracked_files_intent()

        # Only file2.py should be in results (file1.py failed)
        assert len(result) == 1
        assert "file2.py" in result


class TestGetStructuredDiff:
    """Tests for get_structured_diff integration with new fields."""

    @pytest.mark.asyncio
    async def test_structured_diff_preserves_new_file_flags(self, temp_git_repo):
        """Test that get_structured_diff preserves is_new_file and is_deleted flags."""
        git = GitRepoIntegration(temp_git_repo)

        raw_diff = """diff --git a/newfile.py b/newfile.py
new file mode 100644
index 0000000..abcdefg
--- /dev/null
+++ b/newfile.py
@@ -0,0 +1,2 @@
+def new_func():
+    pass
"""

        async def mock_get_git_diff(*args, **kwargs):
            return raw_diff

        with patch.object(git, "get_git_diff", side_effect=mock_get_git_diff):
            result = await git.get_structured_diff()

        assert len(result.files) == 1
        assert result.files[0].is_new_file is True
        assert result.files[0].is_deleted is False
        assert "new file mode" not in result.files[0].diff_content

    @pytest.mark.asyncio
    async def test_structured_diff_with_commit_range(self, temp_git_repo):
        """Test get_structured_diff with commit range includes file flags."""
        git = GitRepoIntegration(temp_git_repo)

        raw_diff = """diff --git a/deleted.py b/deleted.py
deleted file mode 100644
index abcdefg..0000000
--- a/deleted.py
+++ /dev/null
@@ -1,1 +0,0 @@
-old_content
"""

        async def mock_get_git_diff(commit1=None, commit2=None, file_path=None):
            return raw_diff

        with patch.object(git, "get_git_diff", side_effect=mock_get_git_diff):
            result = await git.get_structured_diff(commit1="abc123", commit2="def456")

        assert len(result.files) == 1
        assert result.files[0].is_new_file is False
        assert result.files[0].is_deleted is True
        assert "deleted file mode" not in result.files[0].diff_content


class TestGetDefaultBranch:
    """Tests for get_default_branch method."""

    @pytest.mark.asyncio
    async def test_returns_remote_head_when_available(self, temp_git_repo):
        """Test that remote HEAD is returned when available (repo with remote)."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["remote"]:
                return "origin"
            if args == ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]:
                return "origin/main"
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "origin/main"

    @pytest.mark.asyncio
    async def test_falls_back_to_main_when_no_remote(self, temp_git_repo):
        """Test that 'main' branch is returned when remote HEAD is not available."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["remote"]:
                return ""  # No remotes
            if args == ["rev-parse", "--verify", "refs/heads/main"]:
                return "abc123"  # main branch exists
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "main"

    @pytest.mark.asyncio
    async def test_falls_back_to_master_when_no_main(self, temp_git_repo):
        """Test that 'master' branch is returned when 'main' doesn't exist."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["remote"]:
                return ""  # No remotes
            if args == ["rev-parse", "--verify", "refs/heads/main"]:
                return ""  # main doesn't exist
            if args == ["rev-parse", "--verify", "refs/heads/master"]:
                return "def456"  # master exists
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "master"

    @pytest.mark.asyncio
    async def test_falls_back_to_local_head_as_last_resort(self, temp_git_repo):
        """Test that local HEAD is used as last resort when no common branches exist."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["remote"]:
                return ""  # No remotes
            if args == ["rev-parse", "--verify", "refs/heads/main"]:
                return ""  # main doesn't exist
            if args == ["rev-parse", "--verify", "refs/heads/master"]:
                return ""  # master doesn't exist
            if args == ["symbolic-ref", "--short", "HEAD"]:
                return "develop"  # Current branch is develop
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "develop"

    @pytest.mark.asyncio
    async def test_raises_exception_when_no_branch_detected(self, temp_git_repo):
        """Test that exception is raised when no default branch can be determined."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            return ""  # All detection methods fail

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            with pytest.raises(Exception) as exc_info:
                await git.get_default_branch()

        assert "Unable to determine repository default branch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_returns_remote_head_for_non_origin_remote(self, temp_git_repo):
        """Test that non-origin remotes are used for default branch detection."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["remote"]:
                return "upstream"
            if args == ["symbolic-ref", "--short", "refs/remotes/upstream/HEAD"]:
                return "upstream/main"
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "upstream/main"


class TestListRemotes:
    """Tests for list_remotes method."""

    @pytest.mark.asyncio
    async def test_returns_list_of_remote_names(self, temp_git_repo):
        git = GitRepoIntegration(temp_git_repo)
        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = "origin\nupstream"
            result = await git.list_remotes()
        assert result == ["origin", "upstream"]
        mock_cmd.assert_called_once_with(["remote"], raise_on_error=False, timeout=10.0)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_remotes(self, temp_git_repo):
        git = GitRepoIntegration(temp_git_repo)
        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ""
            result = await git.list_remotes()
        assert result == []


class TestParseRemoteBranch:
    """Tests for parse_remote_branch utility function."""

    def test_returns_remote_and_branch_for_known_remote(self):
        result = parse_remote_branch("origin/main", ["origin"])
        assert result == ("origin", "main")

    def test_handles_non_origin_remote(self):
        result = parse_remote_branch("upstream/develop", ["origin", "upstream"])
        assert result == ("upstream", "develop")

    def test_returns_none_for_local_branch(self):
        result = parse_remote_branch("main", ["origin"])
        assert result is None

    def test_returns_none_for_feature_branch_with_slash(self):
        """Branch names containing '/' that don't match a remote are treated as local."""
        result = parse_remote_branch("feat/my-feature", ["origin"])
        assert result is None

    def test_returns_none_when_no_remotes(self):
        result = parse_remote_branch("origin/main", [])
        assert result is None

    def test_branch_name_preserves_slashes(self):
        """Branch part after remote prefix can itself contain slashes."""
        result = parse_remote_branch("origin/release/v1.0", ["origin"])
        assert result == ("origin", "release/v1.0")


class TestHasCommits:
    """Tests for has_commits method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_repo_has_commits(self, temp_git_repo):
        """Test that has_commits returns True when repo has at least one commit."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["rev-parse", "HEAD"]:
                return "abc123def456"
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.has_commits()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_repo_has_no_commits(self, temp_git_repo):
        """Test that has_commits returns False when repo has no commits."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            return ""  # rev-parse HEAD returns empty for unborn branch

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.has_commits()

        assert result is False


class TestGetForkPoint:
    """Tests for get_fork_point method."""

    @pytest.mark.asyncio
    async def test_fork_point_returns_merge_base(self, temp_git_repo):
        """Test fork point returns the merge-base between branches."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["merge-base", "main", "feature"]:
                return "abc123"
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_fork_point("main", "feature")

        assert result == "abc123"

    @pytest.mark.asyncio
    async def test_fork_point_returns_none_when_no_common_ancestor(self, temp_git_repo):
        """Test fork point returns None when branches have no common ancestor."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["merge-base", "main", "feature"]:
                return ""  # No common ancestor
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_fork_point("main", "feature")

        assert result is None


class TestStashPush:
    """Tests for stash_push method."""

    @pytest.mark.asyncio
    async def test_stash_push_returns_sha(self, temp_git_repo):
        """Test stash_push returns the stash commit SHA."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            if args == ["rev-parse", "stash@{0}"]:
                return "abc123def456"
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.stash_push()

        assert result == "abc123def456"
        assert ["add", "-A"] in calls
        assert ["stash", "push"] in calls
        assert ["rev-parse", "stash@{0}"] in calls

    @pytest.mark.asyncio
    async def test_stash_push_with_untracked_includes_u_flag(self, temp_git_repo):
        """Test stash_push with include_untracked=True adds -u flag."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            if args == ["rev-parse", "stash@{0}"]:
                return "abc123"
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.stash_push(include_untracked=True)

        assert result == "abc123"
        assert ["add", "-A"] in calls
        assert ["stash", "push", "-u"] in calls


class TestStashApply:
    """Tests for stash_apply method."""

    @pytest.mark.asyncio
    async def test_stash_apply_calls_git_with_sha(self, temp_git_repo):
        """Test stash_apply calls git stash apply with the commit SHA."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            await git.stash_apply("abc123def456")

        assert ["stash", "apply", "abc123def456"] in calls


class TestStashStore:
    """Tests for stash_store method."""

    @pytest.mark.asyncio
    async def test_stash_store_calls_git_with_sha(self, temp_git_repo):
        """Test stash_store calls git stash store with the commit SHA."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            await git.stash_store("abc123def456")

        assert ["stash", "store", "abc123def456"] in calls

    @pytest.mark.asyncio
    async def test_stash_store_with_message(self, temp_git_repo):
        """Test stash_store includes message when provided."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            await git.stash_store("abc123def456", message="My stash message")

        assert ["stash", "store", "abc123def456", "-m", "My stash message"] in calls


class TestResetWorkingTree:
    """Tests for reset_working_tree method."""

    @pytest.mark.asyncio
    async def test_reset_working_tree_with_untracked(self, temp_git_repo):
        """Test reset_working_tree runs checkout and clean commands."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            await git.reset_working_tree(include_untracked=True)

        assert ["checkout", "."] in calls
        assert ["clean", "-fd"] in calls

    @pytest.mark.asyncio
    async def test_reset_working_tree_without_untracked(self, temp_git_repo):
        """Test reset_working_tree only runs checkout when include_untracked=False."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            await git.reset_working_tree(include_untracked=False)

        assert ["checkout", "."] in calls
        assert ["clean", "-fd"] not in calls


class TestParseGitLogOutput:
    """Tests for _parse_git_log_output method."""

    def test_parse_empty_output(self, temp_git_repo):
        """Test parsing empty output returns empty list."""
        git = GitRepoIntegration(temp_git_repo)
        result = git._parse_git_log_output("")

        assert result == []

    def test_parse_single_commit_subject_only(self, temp_git_repo):
        """Test parsing single commit with subject only (no body)."""
        git = GitRepoIntegration(temp_git_repo)
        # Format: hash\x00author\x00date\x00subject\x00body\x1e
        output = "abc123\x00John Doe\x002024-01-15 10:00:00 +0000\x00Fix bug in parser\x00\x1e"
        result = git._parse_git_log_output(output)

        assert len(result) == 1
        assert result[0].hash == "abc123"
        assert result[0].author == "John Doe"
        assert result[0].date == "2024-01-15 10:00:00 +0000"
        assert result[0].subject == "Fix bug in parser"
        assert result[0].body is None

    def test_parse_single_commit_with_body(self, temp_git_repo):
        """Test parsing single commit with subject and body."""
        git = GitRepoIntegration(temp_git_repo)
        body_content = "This is a detailed description.\n\nWith multiple lines."
        output = f"abc123\x00John Doe\x002024-01-15\x00Fix bug\x00{body_content}\x1e"
        result = git._parse_git_log_output(output)

        assert len(result) == 1
        assert result[0].subject == "Fix bug"
        assert result[0].body == body_content

    def test_parse_multiple_commits(self, temp_git_repo):
        """Test parsing multiple commits with newlines between records.

        Git inserts a newline after each commit's format output, so the actual
        format is: hash\x00author\x00date\x00subject\x00body\x1e\n
        """
        git = GitRepoIntegration(temp_git_repo)
        # Include \n after \x1e to match actual git output
        output = (
            "abc123\x00John\x002024-01-15\x00First commit\x00Body 1\x1e\n"
            "def456\x00Jane\x002024-01-16\x00Second commit\x00\x1e\n"
            "ghi789\x00Bob\x002024-01-17\x00Third commit\x00Multi\nLine\nBody\x1e"
        )
        result = git._parse_git_log_output(output)

        assert len(result) == 3
        assert result[0].hash == "abc123"
        assert result[0].subject == "First commit"
        assert result[0].body == "Body 1"

        assert result[1].hash == "def456"
        assert result[1].subject == "Second commit"
        assert result[1].body is None

        assert result[2].hash == "ghi789"
        assert result[2].subject == "Third commit"
        assert result[2].body == "Multi\nLine\nBody"

    def test_parse_handles_whitespace_only_body(self, temp_git_repo):
        """Test that whitespace-only body is treated as None."""
        git = GitRepoIntegration(temp_git_repo)
        output = "abc123\x00John\x002024-01-15\x00Subject\x00   \n  \x1e"
        result = git._parse_git_log_output(output)

        assert len(result) == 1
        assert result[0].body is None


class TestGetCommitsInRangeWithFileFilter:
    """Tests for get_commits_in_range with file_paths parameter."""

    @pytest.mark.asyncio
    async def test_get_commits_in_range_without_file_filter(self, temp_git_repo):
        """Test get_commits_in_range without file filter."""
        git = GitRepoIntegration(temp_git_repo)
        output = "abc123\x00John\x002024-01-15\x00Fix bug\x00Body\x1e"

        async def mock_run_git_command(args, **kwargs):
            # Verify no file paths are in the args
            assert "--" not in args
            return output

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_commits_in_range("base", "head")

        assert len(result) == 1
        assert result[0].subject == "Fix bug"

    @pytest.mark.asyncio
    async def test_get_commits_in_range_with_file_filter(self, temp_git_repo):
        """Test get_commits_in_range with file_paths filter."""
        git = GitRepoIntegration(temp_git_repo)
        output = "abc123\x00John\x002024-01-15\x00Update file1\x00\x1e"
        captured_args = []

        async def mock_run_git_command(args, **kwargs):
            captured_args.extend(args)
            return output

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_commits_in_range("base", "head", file_paths=["file1.py", "file2.py"])

        assert len(result) == 1
        # Verify file paths are added after "--"
        assert "--" in captured_args
        dash_index = captured_args.index("--")
        assert "file1.py" in captured_args[dash_index + 1 :]
        assert "file2.py" in captured_args[dash_index + 1 :]


class TestGetConflictedFiles:
    """Tests for get_conflicted_files method."""

    @pytest.mark.asyncio
    async def test_get_conflicted_files_returns_list(self, temp_git_repo):
        """Test get_conflicted_files returns list of conflicted files."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["diff", "--name-only", "--diff-filter=U"]:
                return "file1.py\nfile2.py\n"
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_conflicted_files()

        assert result == ["file1.py", "file2.py"]

    @pytest.mark.asyncio
    async def test_get_conflicted_files_empty_when_no_conflicts(self, temp_git_repo):
        """Test get_conflicted_files returns empty list when no conflicts."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["diff", "--name-only", "--diff-filter=U"]:
                return ""
            return ""

        with patch.object(git, "run_git_command", side_effect=mock_run_git_command):
            result = await git.get_conflicted_files()

        assert result == []


class TestReleaseBranchFromWorktree:
    """Tests for release_branch_from_worktree method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_branch_not_checked_out(self, temp_git_repo):
        """Test returns (None, None) when branch is not checked out anywhere."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_get_checked_out_location(branch):
            return None

        with patch.object(git, "get_checked_out_location", side_effect=mock_get_checked_out_location):
            result = await git.release_branch_from_worktree("feature-branch")

        assert result == BranchReleaseResult(None, None)

    @pytest.mark.asyncio
    async def test_returns_none_when_branch_in_main_repo_with_exclude(self, temp_git_repo):
        """Test returns (None, None) when branch is in main repo and exclude_main_repo=True."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_get_checked_out_location(branch):
            return str(temp_git_repo)  # Main repo path

        with patch.object(git, "get_checked_out_location", side_effect=mock_get_checked_out_location):
            result = await git.release_branch_from_worktree("feature-branch", exclude_main_repo=True)

        assert result == BranchReleaseResult(None, None)

    @pytest.mark.asyncio
    async def test_releases_branch_in_worktree_with_uncommitted_changes(self, temp_git_repo):
        """Test stashes and detaches when branch is in worktree with uncommitted changes."""
        git = GitRepoIntegration(temp_git_repo)
        worktree_path = "/path/to/worktree"
        stash_sha = "abc123def456"
        calls = []

        async def mock_get_checked_out_location(branch):
            return worktree_path

        with (
            patch.object(git, "get_checked_out_location", side_effect=mock_get_checked_out_location),
            patch("devboard.integrations.git.GitRepoIntegration") as MockGit,
        ):
            mock_worktree_git = MockGit.return_value

            async def mock_has_uncommitted():
                calls.append("has_uncommitted_changes")
                return True

            async def mock_stash_push(include_untracked=False):
                calls.append(f"stash_push(include_untracked={include_untracked})")
                return stash_sha

            async def mock_switch_detach():
                calls.append("switch_detach")

            mock_worktree_git.has_uncommitted_changes = mock_has_uncommitted
            mock_worktree_git.stash_push = mock_stash_push
            mock_worktree_git.switch_detach = mock_switch_detach

            result = await git.release_branch_from_worktree("feature-branch")

        assert result.worktree_path == worktree_path
        assert result.stash_sha == stash_sha
        assert "has_uncommitted_changes" in calls
        assert "stash_push(include_untracked=True)" in calls
        assert "switch_detach" in calls

    @pytest.mark.asyncio
    async def test_releases_branch_in_worktree_without_uncommitted_changes(self, temp_git_repo):
        """Test only detaches when branch is in worktree without uncommitted changes."""
        git = GitRepoIntegration(temp_git_repo)
        worktree_path = "/path/to/worktree"
        calls = []

        async def mock_get_checked_out_location(branch):
            return worktree_path

        with (
            patch.object(git, "get_checked_out_location", side_effect=mock_get_checked_out_location),
            patch("devboard.integrations.git.GitRepoIntegration") as MockGit,
        ):
            mock_worktree_git = MockGit.return_value

            async def mock_has_uncommitted():
                calls.append("has_uncommitted_changes")
                return False

            async def mock_switch_detach():
                calls.append("switch_detach")

            mock_worktree_git.has_uncommitted_changes = mock_has_uncommitted
            mock_worktree_git.switch_detach = mock_switch_detach

            result = await git.release_branch_from_worktree("feature-branch")

        assert result.worktree_path == worktree_path
        assert result.stash_sha is None
        assert "has_uncommitted_changes" in calls
        assert "switch_detach" in calls

    @pytest.mark.asyncio
    async def test_releases_branch_in_main_repo_when_not_excluded(self, temp_git_repo):
        """Test releases branch in main repo when exclude_main_repo=False."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_get_checked_out_location(branch):
            return str(temp_git_repo)  # Main repo path

        with (
            patch.object(git, "get_checked_out_location", side_effect=mock_get_checked_out_location),
            patch("devboard.integrations.git.GitRepoIntegration") as MockGit,
        ):
            mock_worktree_git = MockGit.return_value

            async def mock_has_uncommitted():
                calls.append("has_uncommitted_changes")
                return False

            async def mock_switch_detach():
                calls.append("switch_detach")

            mock_worktree_git.has_uncommitted_changes = mock_has_uncommitted
            mock_worktree_git.switch_detach = mock_switch_detach

            result = await git.release_branch_from_worktree("feature-branch", exclude_main_repo=False)

        assert result.worktree_path == str(temp_git_repo)
        assert "switch_detach" in calls


class TestFetch:
    """Tests for fetch() method with branch and timeout parameters."""

    @pytest.mark.asyncio
    async def test_fetch_scoped_to_branch(self, temp_git_repo):
        """Fetch with branch argument passes branch to git command."""
        git = GitRepoIntegration(temp_git_repo)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ""
            await git.fetch(branch="main")

        mock_cmd.assert_called_once_with(["fetch", "origin", "main"], timeout=30.0)

    @pytest.mark.asyncio
    async def test_fetch_without_branch(self, temp_git_repo):
        """Fetch without branch argument does not append branch."""
        git = GitRepoIntegration(temp_git_repo)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ""
            await git.fetch()

        mock_cmd.assert_called_once_with(["fetch", "origin"], timeout=30.0)

    @pytest.mark.asyncio
    async def test_fetch_with_custom_timeout(self, temp_git_repo):
        """Fetch passes custom timeout to _run_git_command."""
        git = GitRepoIntegration(temp_git_repo)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ""
            await git.fetch(branch="main", timeout=10.0)

        mock_cmd.assert_called_once_with(["fetch", "origin", "main"], timeout=10.0)


class TestGetInProgressOperationBranch:
    """Tests for get_in_progress_operation_branch method."""

    @pytest.mark.asyncio
    async def test_rebase_merge_head_name_returns_branch(self, tmp_path):
        """rebase-merge/head-name present returns the stripped branch name."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        rebase_merge_dir = git_dir / "rebase-merge"
        rebase_merge_dir.mkdir()
        (rebase_merge_dir / "head-name").write_text("refs/heads/feature/my-branch\n")

        git = GitRepoIntegration(repo_path)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ".git"
            result = await git.get_in_progress_operation_branch()

        assert result == "feature/my-branch"
        mock_cmd.assert_called_once_with(["rev-parse", "--git-dir"])

    @pytest.mark.asyncio
    async def test_rebase_apply_head_name_returns_branch(self, tmp_path):
        """rebase-apply/head-name present returns the stripped branch name."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        rebase_apply_dir = git_dir / "rebase-apply"
        rebase_apply_dir.mkdir()
        (rebase_apply_dir / "head-name").write_text("refs/heads/bugfix/issue-42\n")

        git = GitRepoIntegration(repo_path)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ".git"
            result = await git.get_in_progress_operation_branch()

        assert result == "bugfix/issue-42"

    @pytest.mark.asyncio
    async def test_no_rebase_files_returns_none(self, tmp_path):
        """No rebase state files present returns None."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        git = GitRepoIntegration(repo_path)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ".git"
            result = await git.get_in_progress_operation_branch()

        assert result is None

    @pytest.mark.asyncio
    async def test_ref_without_refs_heads_prefix_returned_as_is(self, tmp_path):
        """A ref that doesn't start with refs/heads/ is returned unchanged."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        rebase_merge_dir = git_dir / "rebase-merge"
        rebase_merge_dir.mkdir()
        (rebase_merge_dir / "head-name").write_text("some-other-ref\n")

        git = GitRepoIntegration(repo_path)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ".git"
            result = await git.get_in_progress_operation_branch()

        assert result == "some-other-ref"

    @pytest.mark.asyncio
    async def test_rebase_merge_takes_precedence_over_rebase_apply(self, tmp_path):
        """rebase-merge/head-name is checked before rebase-apply/head-name."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        rebase_merge_dir = git_dir / "rebase-merge"
        rebase_merge_dir.mkdir()
        (rebase_merge_dir / "head-name").write_text("refs/heads/merge-branch\n")
        rebase_apply_dir = git_dir / "rebase-apply"
        rebase_apply_dir.mkdir()
        (rebase_apply_dir / "head-name").write_text("refs/heads/apply-branch\n")

        git = GitRepoIntegration(repo_path)

        with patch.object(git, "run_git_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = ".git"
            result = await git.get_in_progress_operation_branch()

        assert result == "merge-branch"


class TestCloneRepo:
    """Tests for clone_repo classmethod."""

    @pytest.mark.asyncio
    async def test_clone_repo_success(self, tmp_path):
        """Test successful cloning of a repository."""
        source_repo = tmp_path / "source_repo"
        source_repo.mkdir()
        # Initialize source repo with a commit
        await GitRepoIntegration.init_repo(source_repo)
        source_git = GitRepoIntegration(source_repo)
        (source_repo / "test.txt").write_text("test content")
        await source_git.add_and_commit("Initial commit")

        target_path = tmp_path / "target_repo"

        # Clone the repo
        cloned_git = await GitRepoIntegration.clone_repo(str(source_repo), target_path)

        # Verify clone was successful
        assert cloned_git.repo_path == target_path
        assert target_path.exists()
        assert (target_path / ".git").exists()
        # Verify content was cloned
        assert (target_path / "test.txt").read_text() == "test content"
        # Verify it has commits
        assert await cloned_git.has_commits()

    @pytest.mark.asyncio
    async def test_clone_repo_returns_git_integration_instance(self, tmp_path):
        """Test that clone_repo returns a GitRepoIntegration instance."""
        source_repo = tmp_path / "source"
        source_repo.mkdir()
        await GitRepoIntegration.init_repo(source_repo)
        source_git = GitRepoIntegration(source_repo)
        (source_repo / "file.txt").write_text("content")
        await source_git.add_and_commit("Initial")

        target_path = tmp_path / "target"
        result = await GitRepoIntegration.clone_repo(str(source_repo), target_path)

        assert isinstance(result, GitRepoIntegration)
        assert result.repo_path == target_path

    @pytest.mark.asyncio
    async def test_clone_repo_fails_with_invalid_url(self, tmp_path):
        """Test that clone_repo raises error for invalid repository URL."""
        target_path = tmp_path / "target"

        with pytest.raises(ShellCommandExecutionError):
            await GitRepoIntegration.clone_repo("https://invalid.url/nonexistent.git", target_path)

    @pytest.mark.asyncio
    async def test_clone_repo_fails_when_target_exists_nonempty(self, tmp_path):
        """Test that clone_repo fails if target directory already exists and is not empty."""
        source_repo = tmp_path / "source"
        source_repo.mkdir()
        await GitRepoIntegration.init_repo(source_repo)
        source_git = GitRepoIntegration(source_repo)
        (source_repo / "file.txt").write_text("content")
        await source_git.add_and_commit("Initial")

        target_path = tmp_path / "target"
        target_path.mkdir()  # Create target directory first
        (target_path / "existing.txt").write_text("existing content")  # Add content so directory is not empty

        with pytest.raises(ShellCommandExecutionError):
            await GitRepoIntegration.clone_repo(str(source_repo), target_path)


class TestInitRepo:
    """Tests for init_repo classmethod."""

    @pytest.mark.asyncio
    async def test_init_repo_success(self, tmp_path):
        """Test successful initialization of a new git repository."""
        repo_path = tmp_path / "new_repo"

        git = await GitRepoIntegration.init_repo(repo_path)

        # Verify repo was initialized
        assert git.repo_path == repo_path
        assert repo_path.exists()
        assert (repo_path / ".git").exists()
        # Verify it's a valid git repo (even if empty)
        validation = await git.validate()
        assert validation.success

    @pytest.mark.asyncio
    async def test_init_repo_creates_parent_directories(self, tmp_path):
        """Test that init_repo creates parent directories if they don't exist."""
        repo_path = tmp_path / "parent" / "subdir" / "new_repo"

        await GitRepoIntegration.init_repo(repo_path)

        assert repo_path.exists()
        assert (repo_path / ".git").exists()

    @pytest.mark.asyncio
    async def test_init_repo_returns_git_integration_instance(self, tmp_path):
        """Test that init_repo returns a GitRepoIntegration instance."""
        repo_path = tmp_path / "repo"
        result = await GitRepoIntegration.init_repo(repo_path)

        assert isinstance(result, GitRepoIntegration)
        assert result.repo_path == repo_path

    @pytest.mark.asyncio
    async def test_init_repo_with_existing_directory(self, tmp_path):
        """Test that init_repo works when directory already exists."""
        repo_path = tmp_path / "existing"
        repo_path.mkdir()

        git = await GitRepoIntegration.init_repo(repo_path)

        assert (repo_path / ".git").exists()
        validation = await git.validate()
        assert validation.success


class TestAddAndCommit:
    """Tests for add_and_commit instance method."""

    @pytest.mark.asyncio
    async def test_add_and_commit_success(self, tmp_path):
        """Test successful add and commit operation."""
        repo_path = tmp_path / "repo"
        git = await GitRepoIntegration.init_repo(repo_path)

        # Add a test file
        (repo_path / "test.txt").write_text("test content")

        # Add and commit
        await git.add_and_commit("Add test file")

        # Verify commit was created
        assert await git.has_commits()
        # Get the log to verify the commit message
        log = await git.get_git_log(max_count=1)
        assert len(log) == 1
        assert log[0].subject == "Add test file"

    @pytest.mark.asyncio
    async def test_add_and_commit_stages_all_changes(self, tmp_path):
        """Test that add_and_commit stages all changes (git add -A)."""
        repo_path = tmp_path / "repo"
        git = await GitRepoIntegration.init_repo(repo_path)

        # Create initial commit
        (repo_path / "file1.txt").write_text("content1")
        await git.add_and_commit("Initial commit")

        # Modify existing file and add new file
        (repo_path / "file1.txt").write_text("modified content")
        (repo_path / "file2.txt").write_text("new file")

        # Add and commit
        await git.add_and_commit("Update files")

        # Get diff from initial commit
        log = await git.get_git_log(max_count=2)
        assert len(log) == 2
        assert log[0].subject == "Update files"

        # Verify both files are in the working directory
        assert (repo_path / "file1.txt").read_text() == "modified content"
        assert (repo_path / "file2.txt").read_text() == "new file"

    @pytest.mark.asyncio
    async def test_add_and_commit_with_special_characters_in_message(self, tmp_path):
        """Test that add_and_commit handles special characters in message."""
        repo_path = tmp_path / "repo"
        git = await GitRepoIntegration.init_repo(repo_path)

        (repo_path / "file.txt").write_text("content")
        message = "Fix: update (feature) & <improve> 'quotes' \"double\""
        await git.add_and_commit(message)

        log = await git.get_git_log(max_count=1)
        assert len(log) == 1
        assert log[0].subject == message

    @pytest.mark.asyncio
    async def test_add_and_commit_with_multiline_message(self, tmp_path):
        """Test that add_and_commit handles single-line messages (no body)."""
        repo_path = tmp_path / "repo"
        git = await GitRepoIntegration.init_repo(repo_path)

        (repo_path / "file.txt").write_text("content")
        message = "Add feature"
        await git.add_and_commit(message)

        log = await git.get_git_log(max_count=1)
        assert len(log) == 1
        assert log[0].subject == message

    @pytest.mark.asyncio
    async def test_add_and_commit_includes_deleted_files(self, tmp_path):
        """Test that add_and_commit stages deleted files (git add -A includes deletions)."""
        repo_path = tmp_path / "repo"
        git = await GitRepoIntegration.init_repo(repo_path)

        # Create initial commit with two files
        (repo_path / "file1.txt").write_text("content1")
        (repo_path / "file2.txt").write_text("content2")
        await git.add_and_commit("Initial commit")

        # Delete one file
        (repo_path / "file2.txt").unlink()

        # Add and commit
        await git.add_and_commit("Delete file2")

        # Verify file is gone in the repo
        assert not (repo_path / "file2.txt").exists()
        assert (repo_path / "file1.txt").exists()

    @pytest.mark.asyncio
    async def test_add_and_commit_requires_files_to_stage(self, tmp_path):
        """Test that add_and_commit on a repo with no changes fails."""
        repo_path = tmp_path / "repo"
        git = await GitRepoIntegration.init_repo(repo_path)

        # Create initial commit
        (repo_path / "file.txt").write_text("content")
        await git.add_and_commit("Initial commit")

        # Try to commit with no changes
        with pytest.raises(ShellCommandExecutionError):
            await git.add_and_commit("Nothing to commit")
