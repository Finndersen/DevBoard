"""Tests for context helper functions."""

from unittest.mock import MagicMock

import pytest

from devboard.agents.roles.context_helpers import build_task_context
from devboard.db.models.task import TaskStatus


@pytest.fixture
def mock_task() -> MagicMock:
    """Create a mock task with all required attributes."""
    task = MagicMock()
    task.title = "Test Task Title"
    task.status = TaskStatus.PLANNING
    task.github_pr_number = 42

    task.codebase.name = "test-codebase"
    task.codebase.repository_url = "https://github.com/test/repo"
    task.codebase.description = "A test codebase"
    task.get_current_workspace_dir.return_value = "/tmp/worktree/test"

    task.project.specification.content = "# Project Spec\n\nProject content."
    task.specification.content = "# Task Spec\n\nTask content."
    task.implementation_plan.content = "# Implementation\n\n1. Step one"
    task.implementation_plan_structured = None

    return task


class TestBuildTaskContext:
    """Tests for build_task_context function."""

    def test_includes_all_sections_by_default(self, mock_task: MagicMock):
        """Test that all sections are included with default parameters."""
        result = build_task_context(mock_task)

        assert "NAME: Test Task Title" in result
        assert "STATUS: planning" in result
        assert "PROJECT SPECIFICATION:" in result
        assert "Project content." in result
        assert "TASK SPECIFICATION:" in result
        assert "Task content." in result
        assert "IMPLEMENTATION PLAN:" in result
        assert "1. Step one" in result
        assert "RELEVANT CODEBASE:" in result
        assert "test-codebase" in result

    def test_excludes_project_specification_when_disabled(self, mock_task: MagicMock):
        """Test that project specification is excluded when flag is False."""
        result = build_task_context(mock_task, include_project_specification=False)

        assert "PROJECT SPECIFICATION:" not in result
        assert "Project content." not in result
        assert "TASK SPECIFICATION:" in result

    def test_excludes_implementation_plan_when_none(self, mock_task: MagicMock):
        """Test that implementation plan is excluded when task has none."""
        mock_task.implementation_plan = None
        result = build_task_context(mock_task)

        assert "IMPLEMENTATION PLAN:" not in result
        assert "TASK SPECIFICATION:" in result

    def test_includes_pr_number_when_present(self, mock_task: MagicMock):
        """Test that PR number is automatically included when present."""
        result = build_task_context(mock_task)

        assert "PULL REQUEST: #42" in result

    def test_excludes_pr_number_when_none(self, mock_task: MagicMock):
        """Test that PR number line is omitted when task has no PR."""
        mock_task.github_pr_number = None
        result = build_task_context(mock_task)

        assert "PULL REQUEST" not in result

    def test_includes_pr_status_when_provided(self, mock_task: MagicMock):
        """Test that PR status is included when provided."""
        pr_status = "**State:** open\n**Merged:** False"
        result = build_task_context(mock_task, pr_status_content=pr_status)

        assert "PR STATUS:" in result
        assert "**State:** open" in result
        assert "**Merged:** False" in result

    def test_excludes_pr_status_when_empty(self, mock_task: MagicMock):
        """Test that PR status section is omitted when empty."""
        result = build_task_context(mock_task, pr_status_content="")

        assert "PR STATUS:" not in result

    def test_handles_empty_project_specification(self, mock_task: MagicMock):
        """Test that empty project specification shows <EMPTY>."""
        mock_task.project.specification.content = None
        result = build_task_context(mock_task)

        assert "PROJECT SPECIFICATION:" in result
        assert "<EMPTY>" in result

    def test_handles_empty_task_specification(self, mock_task: MagicMock):
        """Test that empty task specification shows <EMPTY>."""
        mock_task.specification.content = None
        result = build_task_context(mock_task)

        assert "TASK SPECIFICATION:" in result
        assert "<EMPTY>" in result

    def test_handles_missing_implementation_plan(self, mock_task: MagicMock):
        """Test that missing implementation plan excludes the section."""
        mock_task.implementation_plan = None
        result = build_task_context(mock_task)

        assert "IMPLEMENTATION PLAN:" not in result

    def test_handles_empty_implementation_plan_content(self, mock_task: MagicMock):
        """Test that empty implementation plan content shows <EMPTY>."""
        mock_task.implementation_plan.content = None
        result = build_task_context(mock_task)

        assert "IMPLEMENTATION PLAN:" in result
        assert "<EMPTY>" in result

    def test_handles_missing_repository_url(self, mock_task: MagicMock):
        """Test that missing repository URL shows N/A."""
        mock_task.codebase.repository_url = None
        result = build_task_context(mock_task)

        assert "Repository URL: N/A" in result

    def test_handles_missing_codebase_description(self, mock_task: MagicMock):
        """Test that missing description shows N/A."""
        mock_task.codebase.description = None
        result = build_task_context(mock_task)

        assert "Description: N/A" in result

    def test_section_order_is_consistent(self, mock_task: MagicMock):
        """Test that sections appear in consistent order."""
        result = build_task_context(mock_task, pr_status_content="PR info")

        # Find positions of each section
        task_name_pos = result.find("## TASK DETAILS")
        pr_status_pos = result.find("PR STATUS:")
        project_spec_pos = result.find("PROJECT SPECIFICATION:")
        task_spec_pos = result.find("TASK SPECIFICATION:")
        impl_plan_pos = result.find("IMPLEMENTATION PLAN:")
        codebase_pos = result.find("RELEVANT CODEBASE:")

        # Verify order: metadata -> project_spec -> pr_status -> task_spec -> impl_plan -> codebase
        assert task_name_pos < project_spec_pos < pr_status_pos < task_spec_pos < impl_plan_pos < codebase_pos

    def test_specification_role_configuration(self, mock_task: MagicMock):
        """Test configuration matching TaskSpecificationAgentRole (no impl plan yet)."""
        mock_task.implementation_plan = None
        mock_task.github_pr_number = None
        result = build_task_context(mock_task)

        assert "PROJECT SPECIFICATION:" in result
        assert "TASK SPECIFICATION:" in result
        assert "IMPLEMENTATION PLAN:" not in result
        assert "PULL REQUEST" not in result

    def test_implementation_role_configuration(self, mock_task: MagicMock):
        """Test configuration matching TaskImplementationAgentRole needs."""
        mock_task.github_pr_number = None
        result = build_task_context(mock_task, include_project_specification=False)

        assert "PROJECT SPECIFICATION:" not in result
        assert "TASK SPECIFICATION:" in result
        assert "IMPLEMENTATION PLAN:" in result

    def test_pr_review_role_configuration(self, mock_task: MagicMock):
        """Test configuration matching TaskPRReviewAgentRole needs."""
        result = build_task_context(
            mock_task,
            include_project_specification=False,
            pr_status_content="**State:** open",
        )

        assert "PULL REQUEST: #42" in result
        assert "PR STATUS:" in result
        assert "PROJECT SPECIFICATION:" not in result
        assert "TASK SPECIFICATION:" in result
        assert "IMPLEMENTATION PLAN:" in result

    def test_structured_plan_omits_outcomes_by_default(self, mock_task: MagicMock):
        mock_task.implementation_plan = None

        plan = MagicMock()
        plan.overview = "Test overview"
        step1 = MagicMock()
        step1.step_number = 1
        step1.status = "complete"
        step1.title = "First step"
        step1.type = "code_change"
        step1.dependencies = []
        step1.outcome = "Step 1 completed successfully"
        step2 = MagicMock()
        step2.step_number = 2
        step2.status = "pending"
        step2.title = "Second step"
        step2.type = "validation"
        step2.dependencies = [1]
        step2.outcome = None
        plan.steps = [step1, step2]
        mock_task.implementation_plan_structured = plan

        result = build_task_context(mock_task)

        assert "First step" in result
        assert "Second step" in result
        assert "Step 1 completed successfully" not in result

    def test_structured_plan_includes_outcomes_when_flag_set(self, mock_task: MagicMock):
        mock_task.implementation_plan = None

        plan = MagicMock()
        plan.overview = "Test overview"
        step1 = MagicMock()
        step1.step_number = 1
        step1.status = "complete"
        step1.title = "First step"
        step1.type = "code_change"
        step1.dependencies = []
        step1.outcome = "Step 1 completed successfully"
        step2 = MagicMock()
        step2.step_number = 2
        step2.status = "pending"
        step2.title = "Second step"
        step2.type = "validation"
        step2.dependencies = [1]
        step2.outcome = None
        plan.steps = [step1, step2]
        mock_task.implementation_plan_structured = plan

        result = build_task_context(mock_task, include_step_outcomes=True)

        assert "First step" in result
        assert "Second step" in result
        assert "Step 1 completed successfully" in result

    def test_structured_plan_no_current_step_marker(self, mock_task: MagicMock):
        mock_task.implementation_plan = None

        plan = MagicMock()
        plan.overview = "Test overview"
        step1 = MagicMock()
        step1.step_number = 1
        step1.status = "complete"
        step1.title = "First step"
        step1.type = "code_change"
        step1.dependencies = []
        step1.outcome = "Done"
        step2 = MagicMock()
        step2.step_number = 2
        step2.status = "pending"
        step2.title = "Second step"
        step2.type = "validation"
        step2.dependencies = [1]
        step2.outcome = None
        plan.steps = [step1, step2]
        mock_task.implementation_plan_structured = plan

        result = build_task_context(mock_task)

        assert "CURRENT STEP" not in result
