"""Tests for role event_context_types property."""

from unittest.mock import Mock

from devboard.agents.roles.background_agent import BackgroundAgentRole
from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.project_qa import ProjectQAAgentRole
from devboard.agents.roles.task_planning import TaskPlanningAgentRole
from devboard.agents.roles.task_pr_review import TaskPRReviewAgentRole


def _make_task_planning_role() -> TaskPlanningAgentRole:
    task = Mock()
    task.title = "Test task"
    task.id = 1
    task.status = Mock()
    return TaskPlanningAgentRole(
        task=task,
        document_repository=Mock(),
        agent_config_service=Mock(),
        task_service=Mock(),
        conversation_repo=Mock(),
        conversation_id=None,
        working_dir="/tmp",
        plan_service=Mock(),
    )


def _make_project_qa_role() -> ProjectQAAgentRole:
    project = Mock()
    project.id = 1
    return ProjectQAAgentRole(
        project=project,
        document_repository=Mock(),
        agent_config_service=Mock(),
        task_service=Mock(),
        conversation_repo=Mock(),
        conversation_id=None,
    )


def _make_task_pr_review_role() -> TaskPRReviewAgentRole:
    task = Mock()
    task.id = 1
    task.github_pr_number = 42
    task.codebase = Mock()
    task.codebase.repository_url = "https://github.com/example/repo"
    task.status = Mock()
    return TaskPRReviewAgentRole(
        task=task,
        task_service=Mock(),
        github_integration=Mock(),
        working_dir="/tmp",
        conversation_repo=Mock(),
        agent_config_service=Mock(),
        conversation_id=None,
    )


def _make_background_agent_role() -> BackgroundAgentRole:
    return BackgroundAgentRole(
        system_prompt="You are a background agent.",
        task_service=Mock(),
        conversation_repo=Mock(),
        document_repo=Mock(),
        agent_config_service=Mock(),
        integration_service=Mock(),
        project_repo=Mock(),
        codebase_repo=Mock(),
        background_agent=Mock(),
        conversation_id=None,
        log_entry_service=Mock(),
        background_agent_repo=Mock(),
        agent_run_repo=Mock(),
    )


class TestEventContextTypesProperty:
    def test_base_role_has_empty_event_context_types(self):
        """The default event_context_types on AgentRole base returns empty list."""

        class MinimalRole(AgentRole):
            def get_system_prompt(self) -> str:
                return ""

            def get_tools(self):
                return []

            async def get_context_content(self) -> str:
                return ""

        role = MinimalRole()
        assert role.event_context_types == []

    def test_task_planning_role_event_context_types(self):
        role = _make_task_planning_role()
        assert set(role.event_context_types) == {"task.merged", "document.updated", "project.updated"}

    def test_project_qa_role_event_context_types(self):
        role = _make_project_qa_role()
        assert set(role.event_context_types) == {
            "task.created",
            "task.merged",
            "task.deleted",
            "document.updated",
            "project.updated",
        }

    def test_task_pr_review_role_event_context_types(self):
        role = _make_task_pr_review_role()
        assert role.event_context_types == ["task.merged"]

    def test_background_agent_role_event_context_types(self):
        role = _make_background_agent_role()
        assert set(role.event_context_types) == {
            "task.created",
            "task.merged",
            "document.updated",
            "project.updated",
        }
