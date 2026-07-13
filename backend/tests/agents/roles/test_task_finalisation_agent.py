"""Tests for TaskFinalisationAgentRole."""

from unittest.mock import Mock, patch

import pytest

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles.task_finalisation import TaskFinalisationAgentRole
from devboard.db.models.document import Document, DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import ConversationRepository, DocumentRepository
from devboard.services.task_service import TaskService
from tests.conftest import create_mock_task


@pytest.fixture(autouse=True)
def mock_get_execution_manager():
    """Patch get_execution_manager so role tests don't require app lifespan."""
    with patch("devboard.agents.roles.task_base.get_execution_manager") as mock:
        mock.return_value = Mock()
        yield mock


@pytest.fixture
def mock_task():
    task = create_mock_task(
        task_id=1,
        title="Finalisation Task",
        status=TaskStatus.MERGED,
        specification_content="# Task Specification\n\nContent",
    )
    # Ensure project is treated as a root project (no parent)
    task.project.id = 100
    task.project.name = "Root Project"
    task.project.description = "Root project description"
    task.project.parent = None
    task.project.specification.content = "# Project Spec\n\nProject content."
    return task


@pytest.fixture
def mock_task_in_initiative():
    task = create_mock_task(
        task_id=2,
        title="Initiative Task",
        status=TaskStatus.MERGED,
        specification_content="# Task Specification\n\nInitiative task content",
    )
    # Project is the parent project
    task.project.id = 10
    task.project.name = "Root Project"
    task.project.description = "The root project"
    task.project.specification = Mock()
    task.project.specification.content = "# Root Spec\n\nRoot project overview."

    # Initiative is a separate entity linked to the task
    initiative = Mock()
    initiative.id = 200
    initiative.name = "My Initiative"
    initiative.description = "An initiative under root project"
    initiative.specification = Mock()
    initiative.specification.content = "## Overview\n\nInitiative overview.\n\nMore details here."
    task.initiative = initiative
    task.initiative_id = 200
    return task


@pytest.fixture
def mock_task_service():
    service = Mock(spec=TaskService)
    service.transition_to_complete = Mock()
    service.get_custom_fields = Mock(return_value=[])
    return service


@pytest.fixture
def mock_conversation_repo():
    repo = Mock(spec=ConversationRepository)
    repo.db = Mock()
    return repo


@pytest.fixture
def mock_document_repo():
    repo = Mock(spec=DocumentRepository)
    repo.db = Mock()
    return repo


@pytest.fixture
def mock_agent_config_service():
    return Mock(spec=AgentConfigService)


@pytest.fixture
def role(mock_task, mock_task_service, mock_conversation_repo, mock_document_repo, mock_agent_config_service):
    return TaskFinalisationAgentRole(
        task=mock_task,
        task_service=mock_task_service,
        working_dir="/test/working_dir",
        conversation_repo=mock_conversation_repo,
        agent_config_service=mock_agent_config_service,
        conversation_id=123,
        document_repo=mock_document_repo,
    )


class TestTaskFinalisationAgentRole:
    """Tests for TaskFinalisationAgentRole."""

    def test_role_initialization(self, role, mock_task, mock_document_repo):
        assert role.task == mock_task
        assert role.working_dir == "/test/working_dir"
        assert role.conversation_id == 123
        assert role.document_repo == mock_document_repo

    def test_get_tools_includes_common_task_tools(self, role):
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "list_tasks" in tool_names
        assert "view_task_details" in tool_names
        assert "create_task" in tool_names
        assert "investigate_codebase" in tool_names
        assert "inspect_conversation" in tool_names

    def test_get_tools_includes_finalisation_specific_tools(self, role):
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "edit_project_specification" in tool_names

    def test_get_tools_for_initiative_task_includes_both_context_tools(self, role, mock_task):
        """A task under an initiative can edit both the initiative's context and the parent project."""
        initiative = Mock()
        initiative_spec = Mock(spec=Document)
        initiative_spec.document_type = DocumentType.INITIATIVE_CONTEXT
        initiative_spec.content = "# Initiative"
        initiative.specification = initiative_spec
        mock_task.initiative = initiative

        tool_names = [tool.name for tool in role.get_tools()]

        assert "edit_initiative_context" in tool_names
        assert "edit_project_specification" in tool_names

    def test_get_tools_does_not_include_editing_tools(self, role):
        """Code editing tools should not be present — code is already merged."""
        tools = role.get_tools()
        tool_names = [tool.name for tool in tools]

        assert "merge_branch_and_finalise" not in tool_names
        assert "merge_pr_and_finalise" not in tool_names
        assert "rebase_task_branch" not in tool_names

    def test_allowed_builtin_tools_are_read_only(self, role):
        assert role.allowed_builtin_tools == ["Read", "Grep", "Glob", "WebFetch", "WebSearch"]
        assert "Edit" not in role.allowed_builtin_tools
        assert "Bash" not in role.allowed_builtin_tools
        assert "Write" not in role.allowed_builtin_tools

    def test_include_builtin_system_prompt_is_false(self, role):
        assert role.include_builtin_system_prompt is False

    def test_system_prompt_content(self, role):
        prompt = role.get_system_prompt()
        assert "propose" in prompt.lower()
        assert "plan" in prompt.lower()
        assert "specification" in prompt.lower()

    def test_system_prompt_mentions_parent_entity_update(self, role):
        prompt = role.get_system_prompt()
        assert "parent project" in prompt.lower()
        assert "edit_project_specification" in prompt
        assert "initiative" in prompt.lower()
        assert "feed" in prompt.lower()

    @pytest.mark.asyncio
    async def test_get_context_content(self, role, mock_task):
        content = await role.get_context_content()
        assert isinstance(content, str)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_get_context_content_direct_project_includes_project_spec(
        self,
        role,
        mock_task,
        mock_conversation_repo,
        mock_task_service,
        mock_document_repo,
        mock_agent_config_service,
    ):
        """Task directly in a project gets project specification in context."""
        content = await role.get_context_content()

        assert "# Project" in content
        assert "Root Project" in content
        assert "## Project Specification" in content
        assert "Project content." in content
        assert "# Initiative" not in content
        assert "## Initiative Context" not in content

    @pytest.mark.asyncio
    async def test_get_context_content_in_initiative_includes_hierarchy(
        self,
        mock_task_in_initiative,
        mock_task_service,
        mock_conversation_repo,
        mock_document_repo,
        mock_agent_config_service,
    ):
        """Task in an initiative gets both root project and initiative context."""
        role = TaskFinalisationAgentRole(
            task=mock_task_in_initiative,
            task_service=mock_task_service,
            working_dir="/test/working_dir",
            conversation_repo=mock_conversation_repo,
            agent_config_service=mock_agent_config_service,
            conversation_id=123,
            document_repo=mock_document_repo,
        )

        content = await role.get_context_content()

        assert "# Project" in content
        assert "ID: 10" in content
        assert "Root Project" in content
        assert "## Project Specification" in content
        assert "Root project overview." in content
        assert "# Initiative" in content
        assert "ID: 200" in content
        assert "My Initiative" in content
        assert "## Initiative Context" in content
        assert "Initiative overview." in content
