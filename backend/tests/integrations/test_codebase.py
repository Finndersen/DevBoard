"""Tests for Filesystem and Git integrations."""

from unittest.mock import patch

import pytest

from devboard.integrations.codebase import CodebaseIntegration
from devboard.integrations.git import GitRepoIntegration
from devboard.integrations.shell import ShellCommandResult


@pytest.fixture
def temp_codebase(tmp_path):
    """Create a temporary codebase directory with git repo."""
    codebase_path = tmp_path / "test_codebase"
    codebase_path.mkdir()

    (codebase_path / ".git").mkdir()

    test_file = codebase_path / "test.py"
    test_file.write_text("def hello():\n    print('hello')\n")

    subdir = codebase_path / "subdir"
    subdir.mkdir()
    (subdir / "file.txt").write_text("content")

    return codebase_path


class TestFilesystemIntegrationMethods:
    """Tests for FilesystemIntegration methods."""

    @pytest.mark.asyncio
    async def test_test_connection_success(self, temp_codebase):
        """Test successful connection test."""
        integration = CodebaseIntegration(temp_codebase)
        result = await integration.validate()
        assert result.success is True
        assert "Directory accessible at:" in result.message

    @pytest.mark.asyncio
    async def test_test_connection_nonexistent_path(self):
        """Test connection test with nonexistent path."""
        integration = CodebaseIntegration("/nonexistent/path")
        result = await integration.validate()
        assert result.success is False
        assert "Codebase path does not exist:" in result.message

    @pytest.mark.asyncio
    async def test_read_file(self, temp_codebase):
        """Test reading file contents."""
        integration = CodebaseIntegration(temp_codebase)
        content = await integration.read_file("test.py")
        assert "def hello():" in content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, temp_codebase):
        """Test reading nonexistent file raises FileNotFoundError."""
        integration = CodebaseIntegration(temp_codebase)
        with pytest.raises(FileNotFoundError, match="File not found"):
            await integration.read_file("nonexistent.py")

    @pytest.mark.asyncio
    async def test_read_file_without_line_numbers(self, temp_codebase):
        """Test reading file without line numbers (default)."""
        integration = CodebaseIntegration(temp_codebase)
        content = await integration.read_file("test.py")
        # By default, line numbers should not be included
        lines = content.split("\n")
        assert lines[0] == "def hello():"
        assert not lines[0].startswith("    1→")

    @pytest.mark.asyncio
    async def test_read_file_with_line_numbers(self, temp_codebase):
        """Test reading file with line numbers in output."""
        integration = CodebaseIntegration(temp_codebase)
        content = await integration.read_file("test.py", include_line_numbers=True)
        # Check that line numbers are included in format "  1→content"
        lines = content.split("\n")
        assert lines[0].startswith("    1→")
        assert "def hello():" in lines[0]

    @pytest.mark.asyncio
    async def test_read_file_with_line_range(self, temp_codebase):
        """Test reading specific line range from file."""
        # Create a file with multiple lines
        test_file = temp_codebase / "multiline.py"
        test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")

        integration = CodebaseIntegration(temp_codebase)
        content = await integration.read_file("multiline.py", start_line=2, end_line=4, include_line_numbers=True)

        lines = content.split("\n")
        assert len(lines) == 3
        assert "line 2" in lines[0]
        assert "line 3" in lines[1]
        assert "line 4" in lines[2]
        # Line numbers should be preserved
        assert lines[0].startswith("    2→")
        assert lines[1].startswith("    3→")
        assert lines[2].startswith("    4→")

    @pytest.mark.asyncio
    async def test_read_file_from_start_line(self, temp_codebase):
        """Test reading from specific start line to end of file."""
        test_file = temp_codebase / "multiline.py"
        test_file.write_text("line 1\nline 2\nline 3\n")

        integration = CodebaseIntegration(temp_codebase)
        content = await integration.read_file("multiline.py", start_line=2)

        lines = content.split("\n")
        assert len(lines) == 2
        assert "line 2" in lines[0]
        assert "line 3" in lines[1]

    @pytest.mark.asyncio
    async def test_read_file_to_end_line(self, temp_codebase):
        """Test reading from beginning to specific end line."""
        test_file = temp_codebase / "multiline.py"
        test_file.write_text("line 1\nline 2\nline 3\n")

        integration = CodebaseIntegration(temp_codebase)
        content = await integration.read_file("multiline.py", end_line=2)

        lines = content.split("\n")
        assert len(lines) == 2
        assert "line 1" in lines[0]
        assert "line 2" in lines[1]

    @pytest.mark.asyncio
    async def test_read_file_invalid_range(self, temp_codebase):
        """Test reading with invalid line range raises ValueError."""
        integration = CodebaseIntegration(temp_codebase)

        # start > end
        with pytest.raises(ValueError, match="start_line .* must be <= end_line"):
            await integration.read_file("test.py", start_line=5, end_line=2)

        # negative start
        with pytest.raises(ValueError, match="start_line must be >= 1"):
            await integration.read_file("test.py", start_line=0)

        # negative end
        with pytest.raises(ValueError, match="end_line must be >= 1"):
            await integration.read_file("test.py", end_line=-1)

    @pytest.mark.asyncio
    async def test_read_file_line_beyond_file_length(self, temp_codebase):
        """Test reading with line numbers beyond file length handles gracefully."""
        test_file = temp_codebase / "short.py"
        test_file.write_text("line 1\nline 2\n")

        integration = CodebaseIntegration(temp_codebase)
        # Request lines beyond file length - should return available lines
        content = await integration.read_file("short.py", start_line=1, end_line=100)

        lines = content.split("\n")
        assert len(lines) == 2
        assert "line 1" in lines[0]
        assert "line 2" in lines[1]

    @pytest.mark.asyncio
    async def test_list_directory_contents_files_only(self, temp_codebase):
        """Test listing files in directory (default behavior)."""
        integration = CodebaseIntegration(temp_codebase)
        files = await integration.list_directory_contents("subdir")
        assert "file.txt" in files
        # Should not include directories by default
        assert not any(f.endswith("/") for f in files)

    @pytest.mark.asyncio
    async def test_list_directory_contents_with_directories(self, temp_codebase):
        """Test listing files and directories."""
        # Create nested directory structure
        (temp_codebase / "subdir" / "nested").mkdir()
        (temp_codebase / "subdir" / "nested" / "deep.txt").write_text("deep")

        integration = CodebaseIntegration(temp_codebase)
        entries = await integration.list_directory_contents("subdir", include_directories=True)

        # Should include files
        assert "file.txt" in entries
        assert "nested/deep.txt" in entries
        # Should include directories with trailing /
        assert "nested/" in entries

    @pytest.mark.asyncio
    async def test_list_directory_contents_recursive(self, temp_codebase):
        """Test that listing is recursive."""
        # Create nested structure
        (temp_codebase / "subdir" / "nested").mkdir()
        (temp_codebase / "subdir" / "nested" / "deep.txt").write_text("deep")

        integration = CodebaseIntegration(temp_codebase)
        files = await integration.list_directory_contents("subdir")

        # Should include nested files recursively
        assert "file.txt" in files
        assert "nested/deep.txt" in files

    @pytest.mark.asyncio
    async def test_parse_file_url_with_file_prefix(self, temp_codebase):
        """Test parsing file:// URL."""
        integration = CodebaseIntegration(temp_codebase)
        result = integration.parse_file_url(f"file://{temp_codebase}/test.py")
        assert result == "test.py"

    @pytest.mark.asyncio
    async def test_parse_file_url_with_relative_path(self, temp_codebase):
        """Test parsing relative path."""
        integration = CodebaseIntegration(temp_codebase)
        result = integration.parse_file_url("subdir/file.txt")
        assert result == "subdir/file.txt"


class TestSearchFileContent:
    """Tests for search_file_content method using ripgrep."""

    @pytest.mark.asyncio
    async def test_search_file_content_success(self, temp_codebase):
        """Test successful text search."""
        integration = CodebaseIntegration(temp_codebase)

        rg_output = "test.py:1:def hello():\n"

        mock_result = ShellCommandResult(rg_output, "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result):
            result = await integration.search_file_content("hello")

            assert len(result) == 1
            assert result[0] == "test.py:1:def hello():"

    @pytest.mark.asyncio
    async def test_search_file_content_with_pattern(self, temp_codebase):
        """Test text search with file pattern filter."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("", "", 1)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            result = await integration.search_file_content("hello", file_pattern="*.py")

            call_args = mock_exec.call_args[0][0]
            assert "--glob" in call_args
            assert "*.py" in call_args
            assert result == []

    @pytest.mark.asyncio
    async def test_search_file_content_case_sensitive(self, temp_codebase):
        """Test case sensitive search."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("", "", 1)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            result = await integration.search_file_content("HELLO", case_sensitive=True)

            call_args = mock_exec.call_args[0][0]
            assert "--ignore-case" not in call_args
            assert result == []

    @pytest.mark.asyncio
    async def test_search_file_content_search_hidden(self, temp_codebase):
        """Test search with hidden files enabled."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("", "", 1)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            result = await integration.search_file_content("hello", search_hidden=True)

            call_args = mock_exec.call_args[0][0]
            assert "--no-ignore" in call_args
            assert result == []

    @pytest.mark.asyncio
    async def test_search_file_content_with_subdirectory(self, temp_codebase):
        """Test search with path filter (subdirectory)."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("tests/test_auth.py:10:def test_login():\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            result = await integration.search_file_content("def test_", path="tests")

            # Verify path was passed to rg command
            call_args = mock_exec.call_args[0][0]
            assert "tests" in call_args
            # Verify results are returned
            assert len(result) == 1
            assert "tests/test_auth.py" in result[0]

    @pytest.mark.asyncio
    async def test_search_file_content_subdirectory_with_trailing_slash(self, temp_codebase):
        """Test search handles trailing slash in path."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("backend/models/user.py:5:class User:\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            # Test with trailing slash - should be stripped
            await integration.search_file_content("class", path="backend/models/")

            # Verify trailing slash was removed
            call_args = mock_exec.call_args[0][0]
            assert "backend/models" in call_args
            assert "backend/models/" not in call_args

    @pytest.mark.asyncio
    async def test_search_file_content_with_context_before(self, temp_codebase):
        """Test search with context lines before matches."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("test.py:1:def hello():\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            await integration.search_file_content("def hello", context_before=3)

            # Verify -B flag was passed with correct value
            call_args = mock_exec.call_args[0][0]
            assert "-B" in call_args
            b_index = call_args.index("-B")
            assert call_args[b_index + 1] == "3"

    @pytest.mark.asyncio
    async def test_search_file_content_with_context_after(self, temp_codebase):
        """Test search with context lines after matches."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("test.py:1:def hello():\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            await integration.search_file_content("def hello", context_after=5)

            # Verify -A flag was passed with correct value
            call_args = mock_exec.call_args[0][0]
            assert "-A" in call_args
            a_index = call_args.index("-A")
            assert call_args[a_index + 1] == "5"

    @pytest.mark.asyncio
    async def test_search_file_content_with_both_context(self, temp_codebase):
        """Test search with both before and after context."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("test.py:10:    result = func()\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            await integration.search_file_content("result = ", context_before=2, context_after=3)

            # Verify both -B and -A flags were passed
            call_args = mock_exec.call_args[0][0]
            assert "-B" in call_args
            assert "-A" in call_args
            b_index = call_args.index("-B")
            a_index = call_args.index("-A")
            assert call_args[b_index + 1] == "2"
            assert call_args[a_index + 1] == "3"


class TestSearchFiles:
    """Tests for search_files method using fd."""

    @pytest.mark.asyncio
    async def test_search_files_success(self, temp_codebase):
        """Test successful file search by pattern."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("test.py\nsubdir/file.txt\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result):
            files = await integration.search_files("test")

            assert len(files) == 2
            assert "test.py" in files
            assert "subdir/file.txt" in files

    @pytest.mark.asyncio
    async def test_search_files_with_extension(self, temp_codebase):
        """Test file search with extension filter."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("test.py\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            await integration.search_files("test", extension="py")

            call_args = mock_exec.call_args[0][0]
            assert "--extension" in call_args
            assert "py" in call_args

    @pytest.mark.asyncio
    async def test_search_files_with_exclude(self, temp_codebase):
        """Test file search with exclude pattern."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("test.py\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            await integration.search_files("test", exclude_pattern="*.txt")

            call_args = mock_exec.call_args[0][0]
            assert "--exclude" in call_args
            assert "*.txt" in call_args

    @pytest.mark.asyncio
    async def test_search_files_with_subdirectory(self, temp_codebase):
        """Test file search with subdirectory filter."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("tests/test_auth.py\ntests/test_user.py\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            files = await integration.search_files("test", subdirectory="tests")

            # Verify subdirectory was passed to fd command
            call_args = mock_exec.call_args[0][0]
            assert "tests" in call_args
            # Verify paths include subdirectory (relative to codebase root)
            assert len(files) == 2
            assert "tests/test_auth.py" in files
            assert "tests/test_user.py" in files

    @pytest.mark.asyncio
    async def test_search_files_subdirectory_with_trailing_slash(self, temp_codebase):
        """Test file search handles trailing slash in subdirectory."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("src/components/Button.tsx\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            # Test with trailing slash - should be stripped
            await integration.search_files("Button", subdirectory="src/components/")

            # Verify trailing slash was removed
            call_args = mock_exec.call_args[0][0]
            assert "src/components" in call_args
            assert "src/components/" not in call_args


class TestSearchCodeStructure:
    """Tests for search_code_structure method using ast-grep."""

    @pytest.mark.asyncio
    async def test_search_code_structure_success(self, temp_codebase):
        """Test successful code structure search."""
        integration = CodebaseIntegration(temp_codebase)

        ast_grep_output = "test.py:1:1:def hello():\n"

        mock_result = ShellCommandResult(ast_grep_output, "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result):
            matches = await integration.search_code_structure("def $FUNC($$$ARGS)")

            assert len(matches) == 1
            assert matches[0] == "test.py:1:1:def hello():"

    @pytest.mark.asyncio
    async def test_search_code_structure_with_language(self, temp_codebase):
        """Test code structure search with language filter."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            result = await integration.search_code_structure("class $NAME", language="python")

            call_args = mock_exec.call_args[0][0]
            assert "--lang" in call_args
            assert "python" in call_args
            assert result == []

    @pytest.mark.asyncio
    async def test_search_code_structure_with_path(self, temp_codebase):
        """Test code structure search with path filter."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("backend/models/user.py:5:1:class User:\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            result = await integration.search_code_structure("class $NAME", path="backend/models")

            # Verify path was passed to ast-grep command
            call_args = mock_exec.call_args[0][0]
            assert "backend/models" in call_args
            # Verify results are returned
            assert len(result) == 1
            assert "backend/models/user.py" in result[0]

    @pytest.mark.asyncio
    async def test_search_code_structure_path_with_trailing_slash(self, temp_codebase):
        """Test code structure search handles trailing slash in path."""
        integration = CodebaseIntegration(temp_codebase)

        mock_result = ShellCommandResult("src/components/Button.tsx:10:1:class Button:\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=mock_result) as mock_exec:
            # Test with trailing slash - should be stripped
            await integration.search_code_structure("class $NAME", path="src/components/")

            # Verify trailing slash was removed
            call_args = mock_exec.call_args[0][0]
            assert "src/components" in call_args
            assert "src/components/" not in call_args


class TestGetGitFileTree:
    """Tests for get_git_file_tree method."""

    @pytest.mark.asyncio
    async def test_get_git_file_tree_success(self, temp_codebase):
        """Test successful git file tree generation."""
        integration = CodebaseIntegration(temp_codebase)

        tree_result = ShellCommandResult(".\n├── test.py\n└── subdir\n    └── file.txt\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=tree_result) as mock_exec:
            tree = await integration.get_directory_tree()

            assert "test.py" in tree
            assert "subdir" in tree

            # Verify the method was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert call_args == ["git ls-files | tree --fromfile -F"]

    @pytest.mark.asyncio
    async def test_get_git_file_tree_with_max_depth(self, temp_codebase):
        """Test git file tree with max depth."""
        integration = CodebaseIntegration(temp_codebase)

        tree_result = ShellCommandResult(".\n└── test.py\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=tree_result) as mock_exec:
            await integration.get_directory_tree(max_depth=2)

            # Verify the method was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert call_args == ["git ls-files | tree --fromfile -F -L 2"]

    @pytest.mark.asyncio
    async def test_get_git_file_tree_with_subdirectory(self, temp_codebase):
        """Test git file tree with subdirectory filter."""
        integration = CodebaseIntegration(temp_codebase)

        tree_result = ShellCommandResult("src\n└── main.py\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=tree_result) as mock_exec:
            await integration.get_directory_tree(subdirectory="src")

            # Verify the method was called with subdirectory filter
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert call_args == ["git ls-files 'src/' | tree --fromfile -F"]

    @pytest.mark.asyncio
    async def test_get_git_file_tree_with_subdirectory_and_max_depth(self, temp_codebase):
        """Test git file tree with both subdirectory and max depth."""
        integration = CodebaseIntegration(temp_codebase)

        tree_result = ShellCommandResult("src\n└── components\n    └── Button.js\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=tree_result) as mock_exec:
            await integration.get_directory_tree(max_depth=2, subdirectory="src/components")

            # Verify the method was called with both parameters
            # max_depth=2 + subdirectory_depth=2 = actual_depth=4
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert call_args == ["git ls-files 'src/components/' | tree --fromfile -F -L 4"]

    @pytest.mark.asyncio
    async def test_get_git_file_tree_subdirectory_with_trailing_slash(self, temp_codebase):
        """Test git file tree handles trailing slash in subdirectory."""
        integration = CodebaseIntegration(temp_codebase)

        tree_result = ShellCommandResult("tests\n└── test_main.py\n", "", 0)

        with patch("devboard.integrations.codebase.execute_shell_command", return_value=tree_result) as mock_exec:
            # Test with trailing slash - should be stripped
            await integration.get_directory_tree(subdirectory="tests/")

            # Verify trailing slash was removed
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert call_args == ["git ls-files 'tests/' | tree --fromfile -F"]


class TestDetectGitRemoteUrl:
    """Tests for GitIntegration.detect_git_remote_url method."""

    @pytest.mark.asyncio
    async def test_detect_git_remote_url_success(self, temp_codebase):
        """Test successful git remote URL detection."""
        integration = GitRepoIntegration(temp_codebase)

        origin_result = ShellCommandResult("https://github.com/user/repo.git\n", "", 0)

        with patch("devboard.integrations.git.execute_shell_command", return_value=origin_result) as mock_exec:
            url = await integration.detect_git_remote_url()
            assert url == "https://github.com/user/repo.git"

            # Verify git remote get-url origin was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][0]
            assert call_args == ["git", "remote", "get-url", "origin"]

    @pytest.mark.asyncio
    async def test_detect_git_remote_url_no_origin(self, temp_codebase):
        """Test git remote URL detection when no origin exists."""
        integration = GitRepoIntegration(temp_codebase)

        # First call fails (no origin)
        no_origin_result = ShellCommandResult("", "", 1)
        # Second call lists remotes
        list_remotes_result = ShellCommandResult("upstream\n", "", 0)
        # Third call gets URL of first remote
        get_url_result = ShellCommandResult("https://github.com/user/repo.git\n", "", 0)

        with patch("devboard.integrations.git.execute_shell_command") as mock_exec:
            mock_exec.side_effect = [no_origin_result, list_remotes_result, get_url_result]

            url = await integration.detect_git_remote_url()
            assert url == "https://github.com/user/repo.git"

            # Should have been called 3 times
            assert mock_exec.call_count == 3

    @pytest.mark.asyncio
    async def test_detect_git_remote_url_no_remotes(self, temp_codebase):
        """Test git remote URL detection when no remotes exist."""
        integration = GitRepoIntegration(temp_codebase)

        # Both calls fail
        failed_result = ShellCommandResult("", "", 1)

        with patch("devboard.integrations.git.execute_shell_command", return_value=failed_result):
            url = await integration.detect_git_remote_url()
            assert url is None
