"""Tests for Git integration methods."""

from unittest.mock import patch

import pytest

from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import ShellCommandResult


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
        diff_content = result.files[0].diff_content

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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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
            if args == ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]:
                return "origin/main"
            return ""

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "origin/main"

    @pytest.mark.asyncio
    async def test_falls_back_to_main_when_no_remote(self, temp_git_repo):
        """Test that 'main' branch is returned when remote HEAD is not available."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]:
                return ""  # No remote HEAD
            if args == ["rev-parse", "--verify", "refs/heads/main"]:
                return "abc123"  # main branch exists
            return ""

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "main"

    @pytest.mark.asyncio
    async def test_falls_back_to_master_when_no_main(self, temp_git_repo):
        """Test that 'master' branch is returned when 'main' doesn't exist."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]:
                return ""  # No remote HEAD
            if args == ["rev-parse", "--verify", "refs/heads/main"]:
                return ""  # main doesn't exist
            if args == ["rev-parse", "--verify", "refs/heads/master"]:
                return "def456"  # master exists
            return ""

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "master"

    @pytest.mark.asyncio
    async def test_falls_back_to_local_head_as_last_resort(self, temp_git_repo):
        """Test that local HEAD is used as last resort when no common branches exist."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            if args == ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"]:
                return ""  # No remote HEAD
            if args == ["rev-parse", "--verify", "refs/heads/main"]:
                return ""  # main doesn't exist
            if args == ["rev-parse", "--verify", "refs/heads/master"]:
                return ""  # master doesn't exist
            if args == ["symbolic-ref", "--short", "HEAD"]:
                return "develop"  # Current branch is develop
            return ""

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.get_default_branch()

        assert result == "develop"

    @pytest.mark.asyncio
    async def test_raises_exception_when_no_branch_detected(self, temp_git_repo):
        """Test that exception is raised when no default branch can be determined."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            return ""  # All detection methods fail

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            with pytest.raises(Exception) as exc_info:
                await git.get_default_branch()

        assert "Unable to determine repository default branch" in str(exc_info.value)


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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.has_commits()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_repo_has_no_commits(self, temp_git_repo):
        """Test that has_commits returns False when repo has no commits."""
        git = GitRepoIntegration(temp_git_repo)

        async def mock_run_git_command(args, **kwargs):
            return ""  # rev-parse HEAD returns empty for unborn branch

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.get_fork_point("main", "feature")

        assert result is None


class TestStashPush:
    """Tests for stash_push method."""

    @pytest.mark.asyncio
    async def test_stash_push_returns_stash_ref(self, temp_git_repo):
        """Test stash_push returns stash@{0} reference."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            return ""

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.stash_push()

        assert result == "stash@{0}"
        assert ["stash", "push"] in calls

    @pytest.mark.asyncio
    async def test_stash_push_with_untracked_includes_u_flag(self, temp_git_repo):
        """Test stash_push with include_untracked=True adds -u flag."""
        git = GitRepoIntegration(temp_git_repo)
        calls = []

        async def mock_run_git_command(args, **kwargs):
            calls.append(args)
            return ""

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.stash_push(include_untracked=True)

        assert result == "stash@{0}"
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            await git.reset_working_tree(include_untracked=False)

        assert ["checkout", "."] in calls
        assert ["clean", "-fd"] not in calls


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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
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

        with patch.object(git, "_run_git_command", side_effect=mock_run_git_command):
            result = await git.get_conflicted_files()

        assert result == []
