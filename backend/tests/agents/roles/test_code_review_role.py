"""Tests for CodeReviewAgentRole."""

from unittest.mock import Mock

import pytest

from devboard.agents.roles.code_review import CODE_REVIEW_ROLE_PROMPT, CodeReviewAgentRole
from devboard.db.models.codebase import Codebase


@pytest.fixture
def temp_codebase(tmp_path):
    """Create a temporary codebase directory."""
    codebase_path = tmp_path / "test_codebase"
    codebase_path.mkdir()
    (codebase_path / ".git").mkdir()
    (codebase_path / "main.py").write_text("def main():\n    pass")
    return codebase_path


@pytest.fixture
def mock_codebase(temp_codebase):
    """Create a mock Codebase model."""
    codebase = Mock(spec=Codebase)
    codebase.name = "TestCodebase"
    codebase.description = "A test codebase for review"
    codebase.local_path = str(temp_codebase)
    return codebase


class TestCodeReviewAgentRole:
    """Tests for CodeReviewAgentRole."""

    def test_get_system_prompt(self, mock_codebase):
        """Test role returns the code review system prompt."""
        role = CodeReviewAgentRole(codebase=mock_codebase)

        prompt = role.get_system_prompt()

        assert prompt == CODE_REVIEW_ROLE_PROMPT
        assert "senior code reviewer" in prompt.lower()
        assert "READ-ONLY" in prompt
        assert "Summary" in prompt
        assert "Critical" in prompt

    def test_get_tools_returns_five_readonly_tools(self, mock_codebase):
        """Test role provides 5 read-only codebase tools."""
        role = CodeReviewAgentRole(codebase=mock_codebase)

        tools = role.get_tools()

        assert len(tools) == 5
        tool_names = [tool.name for tool in tools]
        assert "search_file_content" in tool_names
        assert "search_files_by_name" in tool_names
        assert "search_code_structure" in tool_names
        assert "show_directory_tree" in tool_names
        assert "read_file" in tool_names

    def test_allowed_builtin_tools(self, mock_codebase):
        """Test allowed builtin tools is Bash only."""
        role = CodeReviewAgentRole(codebase=mock_codebase)

        assert role.allowed_builtin_tools == ["Bash"]

    def test_uses_worktree_dir_when_provided(self, mock_codebase, tmp_path):
        """Test that worktree_dir overrides codebase.local_path."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").mkdir()

        role = CodeReviewAgentRole(codebase=mock_codebase, worktree_dir=str(worktree))

        assert role._working_dir == str(worktree)

    def test_uses_codebase_local_path_when_no_worktree(self, mock_codebase):
        """Test that codebase.local_path is used when worktree_dir is not provided."""
        role = CodeReviewAgentRole(codebase=mock_codebase)

        assert role._working_dir == mock_codebase.local_path

    @pytest.mark.asyncio
    async def test_context_content_includes_codebase_info(self, mock_codebase):
        """Test context content includes codebase metadata and directory tree."""
        role = CodeReviewAgentRole(codebase=mock_codebase)

        content = await role.get_context_content()

        assert "CODEBASE INFORMATION" in content
        assert "TestCodebase" in content
        assert "A test codebase for review" in content
        assert "DIRECTORY STRUCTURE" in content
