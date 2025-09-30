"""Tests for CodebaseIntegration."""

from unittest.mock import Mock, patch

import pytest

from devboard.integrations.codebase import CodebaseIntegration, detect_git_remote_url
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


class TestCodebaseIntegrationMethods:
    """Tests for CodebaseIntegration methods."""

    @pytest.mark.asyncio
    async def test_test_connection_success(self, temp_codebase):
        """Test successful connection test."""
        integration = CodebaseIntegration(temp_codebase)
        result = await integration.validate()
        assert result.success is True
        assert "Git repository accessible at:" in result.message

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
    async def test_list_files(self, temp_codebase):
        """Test listing files in directory."""
        integration = CodebaseIntegration(temp_codebase)
        files = await integration.list_files("subdir")
        assert "file.txt" in files

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
    """Tests for detect_git_remote_url utility function."""

    def test_detect_git_remote_url_success(self):
        """Test successful git remote URL detection."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "https://github.com/user/repo.git\n"

        with patch("subprocess.run", return_value=mock_result):
            url = detect_git_remote_url("/path/to/repo")
            assert url == "https://github.com/user/repo.git"

    def test_detect_git_remote_url_no_origin(self):
        """Test git remote URL detection when no origin exists."""
        mock_no_origin = Mock()
        mock_no_origin.returncode = 1
        mock_no_origin.stdout = ""

        mock_list_remotes = Mock()
        mock_list_remotes.returncode = 0
        mock_list_remotes.stdout = "upstream\n"

        mock_get_url = Mock()
        mock_get_url.returncode = 0
        mock_get_url.stdout = "https://github.com/user/repo.git\n"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_no_origin, mock_list_remotes, mock_get_url]

            url = detect_git_remote_url("/path/to/repo")
            assert url == "https://github.com/user/repo.git"

    def test_detect_git_remote_url_no_remotes(self):
        """Test git remote URL detection when no remotes exist."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            url = detect_git_remote_url("/path/to/repo")
            assert url is None
