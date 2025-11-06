"""Tests for CodebaseInvestigationRole."""

from unittest.mock import Mock

import pytest

from devboard.agents.roles.codebase_investigation import CodebaseInvestigationRole
from devboard.db.models.codebase import Codebase


@pytest.fixture
def temp_codebase_with_docs(tmp_path):
    """Create a temporary codebase directory with documentation."""
    codebase_path = tmp_path / "test_codebase"
    codebase_path.mkdir()

    # Create .git directory
    (codebase_path / ".git").mkdir()

    # Create docs/INDEX.md
    docs_dir = codebase_path / "docs"
    docs_dir.mkdir()
    index_file = docs_dir / "INDEX.md"
    index_file.write_text("# Documentation Index\n\nThis is the main index.")

    # Create some source files
    (codebase_path / "main.py").write_text("def main():\n    pass")

    return codebase_path


@pytest.fixture
def mock_codebase(temp_codebase_with_docs):
    """Create a mock Codebase model."""
    codebase = Mock(spec=Codebase)
    codebase.name = "TestCodebase"
    codebase.description = "A test codebase"
    codebase.local_path = str(temp_codebase_with_docs)
    return codebase


class TestCodebaseInvestigationRole:
    """Tests for CodebaseInvestigationRole."""

    def test_role_initialization(self, mock_codebase):
        """Test role initializes with correct parameters."""
        role = CodebaseInvestigationRole(codebase=mock_codebase)

        assert role.codebase == mock_codebase
        assert role.codebase_integration is not None
        assert str(role.codebase_integration.codebase_path) == mock_codebase.local_path

    def test_system_prompt(self, mock_codebase):
        """Test role has appropriate system prompt."""
        role = CodebaseInvestigationRole(codebase=mock_codebase)

        prompt = role.get_system_prompt()
        assert "Codebase Investigation Specialist" in prompt
        assert "READ-ONLY" in prompt
        assert "investigation" in prompt.lower()

    def test_get_tools(self, mock_codebase):
        """Test role provides codebase analysis tools."""
        role = CodebaseInvestigationRole(codebase=mock_codebase)

        tools = role.get_tools()

        # Should have all codebase tools including read_file
        assert len(tools) == 5
        tool_names = [tool.name for tool in tools]
        assert "search_text_in_files" in tool_names
        assert "search_files_by_name" in tool_names
        assert "search_code_structure" in tool_names
        assert "show_directory_tree" in tool_names
        assert "read_file" in tool_names

    @pytest.mark.asyncio
    async def test_context_content_includes_codebase_info(self, mock_codebase):
        """Test context content includes codebase information."""
        role = CodebaseInvestigationRole(codebase=mock_codebase)

        content = await role.get_context_content()

        assert "CODEBASE INFORMATION" in content
        assert "TestCodebase" in content
        assert "A test codebase" in content

    @pytest.mark.asyncio
    async def test_context_includes_directory_tree(self, mock_codebase):
        """Test context content includes directory tree."""
        role = CodebaseInvestigationRole(codebase=mock_codebase)

        content = await role.get_context_content()

        assert "DIRECTORY STRUCTURE" in content

    @pytest.mark.asyncio
    async def test_context_includes_docs_index(self, mock_codebase):
        """Test context content includes docs/INDEX.md when it exists."""
        role = CodebaseInvestigationRole(codebase=mock_codebase)

        content = await role.get_context_content()

        assert "DOCUMENTATION INDEX" in content
        assert "This is the main index" in content

    @pytest.mark.asyncio
    async def test_context_handles_missing_docs_index(self, tmp_path):
        """Test context handles missing docs/INDEX.md gracefully."""
        codebase_path = tmp_path / "test_codebase_no_docs"
        codebase_path.mkdir()
        (codebase_path / ".git").mkdir()

        codebase = Mock(spec=Codebase)
        codebase.name = "TestCodebase"
        codebase.description = "No docs"
        codebase.local_path = str(codebase_path)

        role = CodebaseInvestigationRole(codebase=codebase)

        # Should not raise an error even without docs/INDEX.md
        content = await role.get_context_content()

        assert "CODEBASE INFORMATION" in content
        assert "TestCodebase" in content
