"""Tests for codebase exploration tool factory functions."""

from unittest.mock import AsyncMock, Mock

import pytest

from devboard.agents.tools import (
    create_code_structure_search_tool,
    create_directory_tree_tool,
    create_file_search_tool,
    create_text_search_tool,
)
from devboard.integrations.codebase import CodebaseIntegration


@pytest.fixture
def mock_codebase_integration():
    """Create a mock CodebaseIntegration."""
    integration = Mock(spec=CodebaseIntegration)
    integration.search_file_content = AsyncMock()
    integration.search_files = AsyncMock()
    integration.search_code_structure = AsyncMock()
    integration.get_git_file_tree = AsyncMock()
    return integration


class TestTextSearchTool:
    """Tests for create_text_search_tool."""

    def test_tool_creation(self, mock_codebase_integration):
        """Test text search tool is created correctly."""
        tool = create_text_search_tool(mock_codebase_integration)

        assert tool.name == "search_file_content"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_tool_search_success(self, mock_codebase_integration):
        """Test successful text search execution."""
        mock_codebase_integration.search_file_content.return_value = [
            "test.py:1:def hello():",
            "main.py:5:hello()",
        ]

        tool = create_text_search_tool(mock_codebase_integration)
        result = await tool.function("hello")

        assert "test.py:1:def hello():" in result
        assert "main.py:5:hello()" in result

        mock_codebase_integration.search_file_content.assert_called_once_with(
            query="hello",
            file_pattern=None,
            case_sensitive=False,
            search_hidden=False,
            path=None,
            context_before=0,
            context_after=0,
        )

    @pytest.mark.asyncio
    async def test_tool_search_no_matches(self, mock_codebase_integration):
        """Test text search with no matches."""
        mock_codebase_integration.search_file_content.return_value = []

        tool = create_text_search_tool(mock_codebase_integration)
        result = await tool.function("nonexistent")

        assert "No matches found" in result

    @pytest.mark.asyncio
    async def test_tool_search_with_options(self, mock_codebase_integration):
        """Test text search with all options."""
        mock_codebase_integration.search_file_content.return_value = []

        tool = create_text_search_tool(mock_codebase_integration)
        await tool.function(
            "pattern",
            file_pattern="*.py",
            case_sensitive=True,
            search_hidden=True,
        )

        mock_codebase_integration.search_file_content.assert_called_once_with(
            query="pattern",
            file_pattern="*.py",
            case_sensitive=True,
            search_hidden=True,
            path=None,
            context_before=0,
            context_after=0,
        )

    @pytest.mark.asyncio
    async def test_tool_search_limits_results(self, mock_codebase_integration):
        """Test text search limits results to 50."""
        matches = [f"file{i}.py:{i}:line" for i in range(100)]
        mock_codebase_integration.search_file_content.return_value = matches

        tool = create_text_search_tool(mock_codebase_integration)
        result = await tool.function("test")

        # The tool now returns all results joined with newlines
        assert "file0.py:0:line" in result
        assert "file99.py:99:line" in result

    @pytest.mark.asyncio
    async def test_tool_search_error_handling(self, mock_codebase_integration):
        """Test text search error handling."""
        mock_codebase_integration.search_file_content.side_effect = Exception("Search failed")

        tool = create_text_search_tool(mock_codebase_integration)

        # Since generic exception handling was removed, expect the exception to propagate
        with pytest.raises(Exception, match="Search failed"):
            await tool.function("query")


class TestFileSearchTool:
    """Tests for create_file_search_tool."""

    def test_tool_creation(self, mock_codebase_integration):
        """Test file search tool is created correctly."""
        tool = create_file_search_tool(mock_codebase_integration)

        assert tool.name == "search_files_by_name"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_tool_search_success(self, mock_codebase_integration):
        """Test successful file search execution."""
        mock_codebase_integration.search_files.return_value = [
            "test.py",
            "src/test_helper.py",
        ]

        tool = create_file_search_tool(mock_codebase_integration)
        result = await tool.function("test")

        assert "Found 2 files" in result
        assert "test.py" in result
        assert "src/test_helper.py" in result

    @pytest.mark.asyncio
    async def test_tool_search_no_files(self, mock_codebase_integration):
        """Test file search with no matches."""
        mock_codebase_integration.search_files.return_value = []

        tool = create_file_search_tool(mock_codebase_integration)
        result = await tool.function("nonexistent")

        assert "No files found" in result

    @pytest.mark.asyncio
    async def test_tool_search_with_extension(self, mock_codebase_integration):
        """Test file search with extension filter."""
        mock_codebase_integration.search_files.return_value = ["test.py"]

        tool = create_file_search_tool(mock_codebase_integration)
        await tool.function("test", extension="py")

        mock_codebase_integration.search_files.assert_called_once_with(
            pattern="test",
            extension="py",
            exclude_pattern=None,
            search_hidden=False,
            subdirectory=None,
        )

    @pytest.mark.asyncio
    async def test_tool_search_limits_results(self, mock_codebase_integration):
        """Test file search limits results to 100."""
        files = [f"file{i}.py" for i in range(150)]
        mock_codebase_integration.search_files.return_value = files

        tool = create_file_search_tool(mock_codebase_integration)
        result = await tool.function("file")

        assert "Found 150 files" in result
        assert "and 50 more files" in result


class TestCodeStructureSearchTool:
    """Tests for create_code_structure_search_tool."""

    def test_tool_creation(self, mock_codebase_integration):
        """Test code structure search tool is created correctly."""
        tool = create_code_structure_search_tool(mock_codebase_integration)

        assert tool.name == "search_code_structure"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_tool_search_success(self, mock_codebase_integration):
        """Test successful code structure search execution."""
        mock_codebase_integration.search_code_structure.return_value = [
            "test.py:1:0:def hello():",
            "main.py:10:4:def world():",
        ]

        tool = create_code_structure_search_tool(mock_codebase_integration)
        result = await tool.function("def $FUNC($$$ARGS)")

        assert "test.py:1:0:def hello():" in result
        assert "main.py:10:4:def world():" in result

    @pytest.mark.asyncio
    async def test_tool_search_no_matches(self, mock_codebase_integration):
        """Test code structure search with no matches."""
        mock_codebase_integration.search_code_structure.return_value = []

        tool = create_code_structure_search_tool(mock_codebase_integration)
        result = await tool.function("class $NAME")

        assert "No code structure matches found" in result

    @pytest.mark.asyncio
    async def test_tool_search_with_language(self, mock_codebase_integration):
        """Test code structure search with language filter."""
        mock_codebase_integration.search_code_structure.return_value = []

        tool = create_code_structure_search_tool(mock_codebase_integration)
        await tool.function("class $NAME", language="python")

        mock_codebase_integration.search_code_structure.assert_called_once_with(
            pattern="class $NAME",
            language="python",
            path=None,
        )

    @pytest.mark.asyncio
    async def test_tool_search_with_path(self, mock_codebase_integration):
        """Test code structure search with path filter."""
        mock_codebase_integration.search_code_structure.return_value = []

        tool = create_code_structure_search_tool(mock_codebase_integration)
        await tool.function("class $NAME", path="backend/models")

        mock_codebase_integration.search_code_structure.assert_called_once_with(
            pattern="class $NAME",
            language=None,
            path="backend/models",
        )

    @pytest.mark.asyncio
    async def test_tool_search_limits_results(self, mock_codebase_integration):
        """Test code structure search limits results to 50."""
        matches = [f"file{i}.py:{i}:0:def func():" for i in range(100)]
        mock_codebase_integration.search_code_structure.return_value = matches

        tool = create_code_structure_search_tool(mock_codebase_integration)
        result = await tool.function("def $FUNC()")

        # The tool now returns all results joined with newlines
        assert "file0.py:0:0:def func():" in result
        assert "file99.py:99:0:def func():" in result


class TestGitTreeTool:
    """Tests for create_git_tree_tool."""

    def test_tool_creation(self, mock_codebase_integration):
        """Test git tree tool is created correctly."""
        tool = create_directory_tree_tool(mock_codebase_integration)

        assert tool.name == "show_directory_tree"
        assert tool.function is not None

    @pytest.mark.asyncio
    async def test_tool_execution_success(self, mock_codebase_integration):
        """Test successful git tree generation."""
        mock_codebase_integration.get_directory_tree.return_value = ".\n├── test.py\n└── src\n"

        tool = create_directory_tree_tool(mock_codebase_integration)
        result = await tool.function()

        assert "test.py" in result
        assert "src" in result

        mock_codebase_integration.get_directory_tree.assert_called_once_with(max_depth=None, subdirectory=None)

    @pytest.mark.asyncio
    async def test_tool_execution_with_max_depth(self, mock_codebase_integration):
        """Test git tree generation with max depth."""
        mock_codebase_integration.get_directory_tree.return_value = ".\n└── test.py\n"

        tool = create_directory_tree_tool(mock_codebase_integration)
        await tool.function(max_depth=2)

        mock_codebase_integration.get_directory_tree.assert_called_once_with(max_depth=2, subdirectory=None)

    @pytest.mark.asyncio
    async def test_tool_execution_with_subdirectory(self, mock_codebase_integration):
        """Test git tree generation with subdirectory filter."""
        mock_codebase_integration.get_directory_tree.return_value = "src\n└── main.py\n"

        tool = create_directory_tree_tool(mock_codebase_integration)
        await tool.function(subdirectory="src")

        mock_codebase_integration.get_directory_tree.assert_called_once_with(max_depth=None, subdirectory="src")

    @pytest.mark.asyncio
    async def test_tool_execution_with_both_parameters(self, mock_codebase_integration):
        """Test git tree generation with both max_depth and subdirectory."""
        mock_codebase_integration.get_directory_tree.return_value = "tests\n└── test_main.py\n"

        tool = create_directory_tree_tool(mock_codebase_integration)
        await tool.function(max_depth=3, subdirectory="tests")

        mock_codebase_integration.get_directory_tree.assert_called_once_with(max_depth=3, subdirectory="tests")

    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self, mock_codebase_integration):
        """Test git tree error handling."""
        mock_codebase_integration.get_directory_tree.side_effect = Exception("Git error")

        tool = create_directory_tree_tool(mock_codebase_integration)

        # Since generic exception handling was removed, expect the exception to propagate
        with pytest.raises(Exception, match="Git error"):
            await tool.function()
