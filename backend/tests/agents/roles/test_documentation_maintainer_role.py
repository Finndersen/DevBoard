"""Tests for DocumentationMaintainerRole."""

from unittest.mock import Mock

import pytest

from devboard.agents.roles.documentation_maintainer import DocumentationMaintainerRole
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

    # Create docs/MAINTENANCE_GUIDE.md
    maintenance_file = docs_dir / "MAINTENANCE_GUIDE.md"
    maintenance_file.write_text("# Maintenance Guide\n\nGuidelines for maintaining documentation.")

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


@pytest.fixture
def mock_agent_config_service():
    """Create a mock AgentConfigService."""
    return Mock()


class TestDocumentationMaintainerRole:
    """Tests for DocumentationMaintainerRole."""

    def test_role_initialization(self, mock_codebase, mock_agent_config_service):
        """Test role initializes with correct parameters."""
        role = DocumentationMaintainerRole(codebase=mock_codebase, agent_config_service=mock_agent_config_service)

        assert role.codebase == mock_codebase
        assert role.codebase_integration is not None
        assert str(role.codebase_integration.codebase_path) == mock_codebase.local_path
        assert role.agent_config_service == mock_agent_config_service

    def test_system_prompt(self, mock_codebase, mock_agent_config_service):
        """Test role has appropriate system prompt."""
        role = DocumentationMaintainerRole(codebase=mock_codebase, agent_config_service=mock_agent_config_service)

        prompt = role.get_system_prompt()
        assert "Documentation Maintainer" in prompt
        assert "documentation" in prompt.lower()
        assert "High Information Density" in prompt
        assert "Quality Checklist" in prompt

    def test_get_tools(self, mock_codebase, mock_agent_config_service):
        """Test role provides documentation maintenance tools."""
        role = DocumentationMaintainerRole(codebase=mock_codebase, agent_config_service=mock_agent_config_service)

        tools = role.get_tools()

        # Should have codebase tools plus investigation tool plus write/edit tools
        assert len(tools) == 8
        tool_names = [tool.name for tool in tools]
        assert "investigate_codebase" in tool_names
        assert "search_file_content" in tool_names
        assert "search_files_by_name" in tool_names
        assert "search_code_structure" in tool_names
        assert "show_directory_tree" in tool_names
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "edit_file" in tool_names

    @pytest.mark.asyncio
    async def test_context_content_includes_codebase_info(self, mock_codebase, mock_agent_config_service):
        """Test context content includes codebase information."""
        role = DocumentationMaintainerRole(codebase=mock_codebase, agent_config_service=mock_agent_config_service)

        content = await role.get_context_content()

        assert "CODEBASE INFORMATION" in content
        assert "TestCodebase" in content
        assert "A test codebase" in content

    @pytest.mark.asyncio
    async def test_context_includes_directory_tree(self, mock_codebase, mock_agent_config_service):
        """Test context content includes directory tree."""
        role = DocumentationMaintainerRole(codebase=mock_codebase, agent_config_service=mock_agent_config_service)

        content = await role.get_context_content()

        assert "DIRECTORY STRUCTURE" in content

    @pytest.mark.asyncio
    async def test_context_includes_docs_index(self, mock_codebase, mock_agent_config_service):
        """Test context content includes docs/INDEX.md when it exists."""
        role = DocumentationMaintainerRole(codebase=mock_codebase, agent_config_service=mock_agent_config_service)

        content = await role.get_context_content()

        assert "DOCUMENTATION INDEX" in content
        assert "This is the main index" in content

    @pytest.mark.asyncio
    async def test_context_includes_maintenance_guide(self, mock_codebase, mock_agent_config_service):
        """Test context content includes MAINTENANCE_GUIDE.md when it exists."""
        role = DocumentationMaintainerRole(codebase=mock_codebase, agent_config_service=mock_agent_config_service)

        content = await role.get_context_content()

        assert "DOCUMENTATION MAINTENANCE GUIDE" in content
        assert "Guidelines for maintaining documentation" in content

    @pytest.mark.asyncio
    async def test_context_handles_missing_maintenance_guide(self, tmp_path, mock_agent_config_service):
        """Test context handles missing MAINTENANCE_GUIDE.md gracefully."""
        codebase_path = tmp_path / "test_codebase_no_maintenance"
        codebase_path.mkdir()
        (codebase_path / ".git").mkdir()

        # Create docs dir with INDEX.md only
        docs_dir = codebase_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "INDEX.md").write_text("# Index")

        codebase = Mock(spec=Codebase)
        codebase.name = "TestCodebase"
        codebase.description = "No maintenance guide"
        codebase.local_path = str(codebase_path)

        role = DocumentationMaintainerRole(codebase=codebase, agent_config_service=mock_agent_config_service)

        # Should not raise an error even without MAINTENANCE_GUIDE.md
        content = await role.get_context_content()

        assert "CODEBASE INFORMATION" in content
        assert "DOCUMENTATION INDEX" in content
        assert "DOCUMENTATION MAINTENANCE GUIDE" not in content

    @pytest.mark.asyncio
    async def test_context_handles_missing_docs_entirely(self, tmp_path, mock_agent_config_service):
        """Test context handles missing docs/ directory gracefully."""
        codebase_path = tmp_path / "test_codebase_no_docs"
        codebase_path.mkdir()
        (codebase_path / ".git").mkdir()

        codebase = Mock(spec=Codebase)
        codebase.name = "TestCodebase"
        codebase.description = "No docs"
        codebase.local_path = str(codebase_path)

        role = DocumentationMaintainerRole(codebase=codebase, agent_config_service=mock_agent_config_service)

        # Should not raise an error even without docs directory
        content = await role.get_context_content()

        assert "CODEBASE INFORMATION" in content
        assert "TestCodebase" in content
        assert "DOCUMENTATION INDEX" not in content
        assert "DOCUMENTATION MAINTENANCE GUIDE" not in content
