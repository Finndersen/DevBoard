"""Tests for Task PR Review Agent Role."""

from unittest.mock import Mock, patch

import pytest

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.task_pr_review import TaskPRReviewAgentRole
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import ConversationRepository
from devboard.integrations.github import GitHubIntegration
from devboard.services.task_service import TaskService
from tests.conftest import create_mock_task


@pytest.fixture(autouse=True)
def mock_get_execution_manager():
    """Patch get_execution_manager so role tests don't require app lifespan."""
    with patch("devboard.agents.roles.task_base.get_execution_manager") as mock:
        mock.return_value = Mock()
        yield mock


def create_mock_pr_task(task_id: int = 1) -> Mock:
    """Create a mock task configured for PR review (with github_pr_number and repository_url)."""
    task = create_mock_task(
        task_id=task_id,
        title="PR Review Task",
        status=TaskStatus.PR_OPEN,
        specification_content="# Task Specification\n\nContent",
    )
    task.github_pr_number = 42
    task.codebase.repository_url = "https://github.com/org/repo"
    return task


class TestTaskPRReviewAgentRole:
    """Tests for TaskPRReviewAgentRole."""

    @pytest.fixture
    def mock_task(self):
        return create_mock_pr_task()

    @pytest.fixture
    def mock_task_service(self):
        service = Mock(spec=TaskService)
        service.get_custom_fields.return_value = []
        return service

    @pytest.fixture
    def mock_github_integration(self):
        return Mock(spec=GitHubIntegration)

    @pytest.fixture
    def mock_agent_config_service(self):
        return Mock(spec=AgentConfigService)

    @pytest.fixture
    def mock_conversation_repo(self):
        repo = Mock(spec=ConversationRepository)
        repo.db = Mock()
        return repo

    @pytest.fixture
    def role(
        self, mock_task, mock_task_service, mock_github_integration, mock_agent_config_service, mock_conversation_repo
    ):
        return TaskPRReviewAgentRole(
            task=mock_task,
            task_service=mock_task_service,
            github_integration=mock_github_integration,
            working_dir="/test/working_dir",
            conversation_repo=mock_conversation_repo,
            agent_config_service=mock_agent_config_service,
            conversation_id=123,
        )

    def test_role_initialization(self, role, mock_task):
        """Test role stores all expected attributes."""
        assert role.task == mock_task
        assert role.working_dir == "/test/working_dir"
        assert role.conversation_id == 123

    def test_validation_requires_pr_number(
        self, mock_task_service, mock_github_integration, mock_agent_config_service, mock_conversation_repo
    ):
        """Test that role raises ValueError when task has no PR number."""
        task = create_mock_pr_task()
        task.github_pr_number = None

        with pytest.raises(ValueError, match="github_pr_number"):
            TaskPRReviewAgentRole(
                task=task,
                task_service=mock_task_service,
                github_integration=mock_github_integration,
                working_dir="/test/working_dir",
                conversation_repo=mock_conversation_repo,
                agent_config_service=mock_agent_config_service,
                conversation_id=None,
            )

    def test_validation_requires_repository_url(
        self, mock_task_service, mock_github_integration, mock_agent_config_service, mock_conversation_repo
    ):
        """Test that role raises ValueError when codebase has no repository_url."""
        task = create_mock_pr_task()
        task.codebase.repository_url = None

        with pytest.raises(ValueError, match="repository_url"):
            TaskPRReviewAgentRole(
                task=task,
                task_service=mock_task_service,
                github_integration=mock_github_integration,
                working_dir="/test/working_dir",
                conversation_repo=mock_conversation_repo,
                agent_config_service=mock_agent_config_service,
                conversation_id=None,
            )

    def test_get_tools_includes_common_task_tools(self, role):
        """Test that PR review role includes the common task tools from base class."""
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names
        assert "create_task" in tool_names
        assert "investigate_codebase" in tool_names

    def test_get_tools_includes_pr_specific_tools(self, role):
        """Test that PR review role includes its role-specific PR tools."""
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "get_pr_status" in tool_names
        assert "get_pr_feedback" in tool_names
        assert "merge_pr_and_finalise" in tool_names

    def test_get_tools_total_count(self, role):
        """Test the total number of tools returned."""
        tools = role.get_tools()
        # 4 common (list_tasks, view_task_details, create_task, investigate_codebase)
        # + 2 codebase tools (view_codebase_details, update_codebase)
        # + inspect_conversation
        # + 5 PR-specific (get_pr_status, get_pr_feedback, code_structure_search, directory_tree, merge_pr_and_finalise)
        assert len(tools) == 12

    def test_system_prompt_content(self, role):
        """Test role has appropriate system prompt."""
        prompt = role.get_system_prompt()
        assert "Pull Request" in prompt
        assert "PR" in prompt

    @pytest.mark.asyncio
    async def test_get_context_content(self, role, mock_task):
        """Test context content is generated."""
        content = await role.get_context_content()
        assert isinstance(content, str)
        assert len(content) > 0
