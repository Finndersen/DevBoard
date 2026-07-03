"""Tests for context helper functions."""

from unittest.mock import MagicMock

import pytest

from devboard.agents.roles.context_helpers import build_execution_graph_context, build_task_context
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
    task.codebase.developer_context = None
    task.project.specification.content = "# Project Spec\n\nProject content."
    task.specification.content = "# Task Spec\n\nTask content."
    task.implementation_plan.content = "# Implementation\n\n1. Step one"
    task.implementation_plan_structured = None

    return task


class TestBuildTaskContext:
    """Tests for build_task_context function."""

    def test_includes_all_sections_by_default(self, mock_task: MagicMock):
        """Test that all sections are included with default parameters."""
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "Name: Test Task Title" in result
        assert "Status: planning" in result
        assert "## Project Specification" in result
        assert "Project content." in result
        assert "## Task Specification" in result
        assert "Task content." in result
        assert "## Implementation Plan" in result
        assert "1. Step one" in result
        assert "# Codebase" in result
        assert "test-codebase" in result

    def test_excludes_project_specification_when_disabled(self, mock_task: MagicMock):
        """Test that project specification is excluded when flag is False."""
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test", include_project_specification=False)

        assert "## Project Specification" not in result
        assert "Project content." not in result
        assert "## Task Specification" in result

    def test_excludes_implementation_plan_when_none(self, mock_task: MagicMock):
        """Test that implementation plan is excluded when task has none."""
        mock_task.implementation_plan = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "## Implementation Plan" not in result
        assert "## Task Specification" in result

    def test_includes_pr_number_when_present(self, mock_task: MagicMock):
        """Test that PR number is automatically included when present."""
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "PR: #42" in result

    def test_excludes_pr_number_when_none(self, mock_task: MagicMock):
        """Test that PR number line is omitted when task has no PR."""
        mock_task.github_pr_number = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "PR:" not in result

    def test_handles_empty_project_specification(self, mock_task: MagicMock):
        """Test that empty project specification shows <EMPTY>."""
        mock_task.project.specification.content = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "## Project Specification" in result
        assert "<EMPTY>" in result

    def test_handles_empty_task_specification(self, mock_task: MagicMock):
        """Test that empty task specification shows <EMPTY>."""
        mock_task.specification.content = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "## Task Specification" in result
        assert "<EMPTY>" in result

    def test_handles_missing_implementation_plan(self, mock_task: MagicMock):
        """Test that missing implementation plan excludes the section."""
        mock_task.implementation_plan = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "## Implementation Plan" not in result

    def test_handles_empty_implementation_plan_content(self, mock_task: MagicMock):
        """Test that empty implementation plan content shows <EMPTY>."""
        mock_task.implementation_plan.content = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "## Implementation Plan" in result
        assert "<EMPTY>" in result

    def test_handles_missing_repository_url(self, mock_task: MagicMock):
        """Test that missing repository URL shows N/A."""
        mock_task.codebase.repository_url = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "Repository URL: N/A" in result

    def test_handles_missing_codebase_description(self, mock_task: MagicMock):
        """Test that missing description shows N/A."""
        mock_task.codebase.description = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "Description: N/A" in result

    def test_includes_developer_context_when_present(self, mock_task: MagicMock):
        """Test that developer context is included when set."""
        mock_task.codebase.developer_context = "## Testing\n- Run: pytest"
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "## Developer Context" in result
        assert "## Testing\n- Run: pytest" in result

    def test_omits_developer_context_when_none(self, mock_task: MagicMock):
        """Test that developer context section is omitted when None."""
        mock_task.codebase.developer_context = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "Developer Context" not in result

    def test_omits_developer_context_when_empty_string(self, mock_task: MagicMock):
        """Test that developer context section is omitted when empty string."""
        mock_task.codebase.developer_context = ""
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "Developer Context" not in result

    def test_section_order_is_consistent(self, mock_task: MagicMock):
        """Test that sections appear in consistent order."""
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        # Find positions of each section
        project_pos = result.find("# Project")
        project_spec_pos = result.find("## Project Specification")
        codebase_pos = result.find("# Codebase")
        task_pos = result.find("# Task")
        task_spec_pos = result.find("## Task Specification")
        impl_plan_pos = result.find("## Implementation Plan")

        # Verify order: project -> project_spec -> codebase -> task -> task_spec -> impl_plan
        assert project_pos < project_spec_pos < codebase_pos < task_pos < task_spec_pos < impl_plan_pos

    def test_specification_role_configuration(self, mock_task: MagicMock):
        """Test configuration matching TaskSpecificationAgentRole (no impl plan yet)."""
        mock_task.implementation_plan = None
        mock_task.github_pr_number = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "## Project Specification" in result
        assert "## Task Specification" in result
        assert "## Implementation Plan" not in result
        assert "PR:" not in result

    def test_implementation_role_configuration(self, mock_task: MagicMock):
        """Test configuration matching TaskImplementationAgentRole needs."""
        mock_task.github_pr_number = None
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test", include_project_specification=False)

        assert "## Project Specification" not in result
        assert "## Task Specification" in result
        assert "## Implementation Plan" in result

    def test_pr_review_role_configuration(self, mock_task: MagicMock):
        """Test configuration matching TaskPRReviewAgentRole needs."""
        result = build_task_context(
            mock_task,
            working_dir="/tmp/worktree/test",
            include_project_specification=False,
        )

        assert "PR: #42" in result
        assert "## Project Specification" not in result
        assert "## Task Specification" in result
        assert "## Implementation Plan" in result

    def test_step_execution_role_configuration(self, mock_task: MagicMock):
        """Test configuration matching StepExecutionAgentRole needs."""
        result = build_task_context(
            mock_task,
            working_dir="/tmp/worktree/test",
            include_project_specification=False,
            include_step_outcomes=True,
        )

        assert "## Project Specification" not in result
        assert "## Task Specification" in result
        assert "## Implementation Plan" in result

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

        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

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

        result = build_task_context(mock_task, working_dir="/tmp/worktree/test", include_step_outcomes=True)

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

        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "CURRENT STEP" not in result

    def test_excludes_implementation_plan_when_flag_is_false(self, mock_task: MagicMock):
        """Test that implementation plan is excluded when include_implementation_plan=False."""
        result = build_task_context(mock_task, working_dir="/tmp/worktree/test", include_implementation_plan=False)

        assert "## Implementation Plan" not in result
        assert "## Task Specification" in result

    def test_excludes_step_status_when_flag_is_false(self, mock_task: MagicMock):
        """Test that step status is excluded from structured plan when include_step_status=False."""
        mock_task.implementation_plan = None

        plan = MagicMock()
        plan.overview = "Test overview"
        step1 = MagicMock()
        step1.step_number = 1
        step1.status = "complete"
        step1.title = "First step"
        step1.type = "code_change"
        step1.dependencies = []
        step1.outcome = None
        plan.steps = [step1]
        mock_task.implementation_plan_structured = plan

        result = build_task_context(mock_task, working_dir="/tmp/worktree/test", include_step_status=False)

        assert "First step" in result
        assert "[complete]" not in result

    def test_includes_step_status_by_default(self, mock_task: MagicMock):
        """Test that step status is included by default."""
        mock_task.implementation_plan = None

        plan = MagicMock()
        plan.overview = None
        step1 = MagicMock()
        step1.step_number = 1
        step1.status = "pending"
        step1.title = "First step"
        step1.type = "code_change"
        step1.dependencies = []
        step1.outcome = None
        plan.steps = [step1]
        mock_task.implementation_plan_structured = plan

        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "[pending]" in result

    def test_structured_plan_does_not_include_execution_graph(self, mock_task: MagicMock):
        mock_task.implementation_plan = None

        plan = MagicMock()
        plan.overview = "Test overview"
        step1 = MagicMock()
        step1.step_number = 1
        step1.status = "pending"
        step1.title = "First step"
        step1.type = "code_change"
        step1.dependencies = []
        step1.outcome = None
        plan.steps = [step1]
        mock_task.implementation_plan_structured = plan

        result = build_task_context(mock_task, working_dir="/tmp/worktree/test")

        assert "EXECUTION GRAPH" not in result

    def test_includes_working_dir_in_codebase_info(self, mock_task: MagicMock):
        """Test that working_dir is used for codebase worktree directory."""
        result = build_task_context(mock_task, working_dir="/custom/working/dir")

        assert "Worktree directory: /custom/working/dir" in result

    def test_global_context_prepended_when_provided(self, mock_task: MagicMock):
        """Non-empty global context appears as first section before project metadata."""
        gc = "Domain: SaaS platform for developers."
        result = build_task_context(mock_task, working_dir="/tmp/worktree", global_context=gc)

        assert "# Global Context" in result
        assert "<document>" in result
        assert gc in result
        # Global context must appear before project metadata
        assert result.index("# Global Context") < result.index("# Project")

    def test_global_context_omitted_when_none(self, mock_task: MagicMock):
        """No global context section when global_context is None."""
        result = build_task_context(mock_task, working_dir="/tmp/worktree", global_context=None)

        assert "# Global Context" not in result

    def test_global_context_omitted_when_empty_string(self, mock_task: MagicMock):
        """No global context section when global_context is empty string."""
        result = build_task_context(mock_task, working_dir="/tmp/worktree", global_context="")

        assert "# Global Context" not in result


def _make_step(
    number: int, *, status: str = "pending", dependencies: list[int] | None = None, title: str = ""
) -> MagicMock:
    step = MagicMock()
    step.step_number = number
    step.status = status
    step.title = title or f"Step {number}"
    step.dependencies = dependencies or []
    return step


def _make_task_with_steps(steps: list[MagicMock]) -> MagicMock:
    task = MagicMock()
    plan = MagicMock()
    plan.steps = steps
    task.implementation_plan_structured = plan
    return task


class TestBuildExecutionGraphContextStepStatus:
    """Tests for include_step_status parameter of build_execution_graph_context."""

    def test_excludes_step_status_when_flag_is_false(self):
        steps = [_make_step(1, status="complete"), _make_step(2, status="pending", dependencies=[1])]
        task = _make_task_with_steps(steps)

        result = build_execution_graph_context(task, include_step_status=False)

        assert "Step 1: Step 1" in result
        assert "[complete]" not in result
        assert "[pending]" not in result

    def test_includes_step_status_by_default(self):
        steps = [_make_step(1, status="complete")]
        task = _make_task_with_steps(steps)

        result = build_execution_graph_context(task)

        assert "[complete]" in result


class TestBuildExecutionGraphContext:
    """Tests for build_execution_graph_context function."""

    def test_independent_steps_same_layer(self):
        steps = [_make_step(1), _make_step(2), _make_step(3)]
        task = _make_task_with_steps(steps)

        result = build_execution_graph_context(task)

        assert "Layer 1 (can run in parallel):" in result
        assert "Step 1" in result
        assert "Step 2" in result
        assert "Step 3" in result
        assert "Layer 2" not in result

    def test_chain_dependencies_separate_layers(self):
        steps = [
            _make_step(1),
            _make_step(2, dependencies=[1]),
            _make_step(3, dependencies=[2]),
        ]
        task = _make_task_with_steps(steps)

        result = build_execution_graph_context(task)

        assert "Layer 1:" in result
        assert "Layer 2:" in result
        assert "Layer 3:" in result

        # Verify ordering within layers
        layer1_pos = result.find("Layer 1")
        layer2_pos = result.find("Layer 2")
        layer3_pos = result.find("Layer 3")
        step1_pos = result.find("Step 1:")
        step2_pos = result.find("Step 2:")
        step3_pos = result.find("Step 3:")

        assert layer1_pos < step1_pos < layer2_pos < step2_pos < layer3_pos < step3_pos

    def test_all_complete_steps_still_respect_dependency_ordering(self):
        steps = [
            _make_step(1, status="complete"),
            _make_step(2, status="complete", dependencies=[1]),
            _make_step(3, status="complete", dependencies=[2]),
        ]
        task = _make_task_with_steps(steps)

        result = build_execution_graph_context(task)

        # Even though all steps are complete, they must be in separate layers
        assert "Layer 1:" in result
        assert "Layer 2:" in result
        assert "Layer 3:" in result

    def test_parallel_steps_with_shared_dependency(self):
        steps = [
            _make_step(1),
            _make_step(2, dependencies=[1]),
            _make_step(3, dependencies=[1]),
            _make_step(4, dependencies=[2, 3]),
        ]
        task = _make_task_with_steps(steps)

        result = build_execution_graph_context(task)

        assert "Layer 1:" in result
        assert "Layer 2 (can run in parallel):" in result
        assert "Layer 3:" in result

    def test_empty_plan_returns_empty_string(self):
        task = MagicMock()
        task.implementation_plan_structured = None

        result = build_execution_graph_context(task)

        assert result == ""

    def test_no_steps_returns_empty_string(self):
        task = MagicMock()
        plan = MagicMock()
        plan.steps = []
        task.implementation_plan_structured = plan

        result = build_execution_graph_context(task)

        assert result == ""
