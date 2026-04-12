"""Tests for CodeReviewAgentRole."""

from unittest.mock import Mock, patch

import pytest

from devboard.agents.roles.code_review import CODE_REVIEW_ROLE_PROMPT, CodeReviewAgentRole
from devboard.db.models import Task
from devboard.db.models.codebase import Codebase


@pytest.fixture
def temp_codebase_path(tmp_path):
    """Create a temporary codebase directory."""
    codebase_path = tmp_path / "test_codebase"
    codebase_path.mkdir()
    (codebase_path / ".git").mkdir()
    (codebase_path / "main.py").write_text("def main():\n    pass")
    return codebase_path


@pytest.fixture
def mock_task(temp_codebase_path):
    """Create a mock Task with a codebase."""
    codebase = Mock(spec=Codebase)
    codebase.name = "TestCodebase"
    codebase.description = "A test codebase for review"
    codebase.local_path = str(temp_codebase_path)

    task = Mock(spec=Task)
    task.codebase = codebase
    return task


class TestCodeReviewAgentRole:
    """Tests for CodeReviewAgentRole."""

    def test_get_system_prompt(self, mock_task):
        """Test role returns the code review system prompt."""
        role = CodeReviewAgentRole(task=mock_task, working_dir=str(mock_task.codebase.local_path))

        prompt = role.get_system_prompt()

        assert prompt == CODE_REVIEW_ROLE_PROMPT
        assert "senior code reviewer" in prompt.lower()
        assert "READ-ONLY" in prompt
        assert "Summary" in prompt
        assert "Critical" in prompt

    def test_get_tools_returns_five_readonly_tools(self, mock_task):
        """Test role provides 5 read-only codebase tools."""
        role = CodeReviewAgentRole(task=mock_task, working_dir=str(mock_task.codebase.local_path))

        tools = role.get_tools()

        assert len(tools) == 5
        tool_names = [tool.name for tool in tools]
        assert "search_file_content" in tool_names
        assert "search_files_by_name" in tool_names
        assert "search_code_structure" in tool_names
        assert "show_directory_tree" in tool_names
        assert "read_file" in tool_names

    def test_allowed_builtin_tools(self, mock_task):
        """Test allowed builtin tools includes Bash and read-only tools."""
        role = CodeReviewAgentRole(task=mock_task, working_dir=str(mock_task.codebase.local_path))

        assert role.allowed_builtin_tools == ["Bash", "Skill", "Read", "Grep", "Glob"]

    def test_uses_provided_working_dir(self, mock_task, tmp_path):
        """Test that the provided working_dir is used for codebase integration."""
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        role = CodeReviewAgentRole(task=mock_task, working_dir=str(worktree))

        assert role._codebase_integration.codebase_path == worktree.resolve()

    @pytest.mark.asyncio
    async def test_context_content_uses_build_task_context(self, mock_task):
        """Test context content delegates to build_task_context."""
        role = CodeReviewAgentRole(task=mock_task, working_dir=str(mock_task.codebase.local_path))

        with patch("devboard.agents.roles.code_review.build_task_context", return_value="mocked context") as mock_build:
            content = await role.get_context_content()

        mock_build.assert_called_once_with(
            mock_task, working_dir=str(mock_task.codebase.local_path), include_step_outcomes=True
        )
        assert content == "mocked context"
