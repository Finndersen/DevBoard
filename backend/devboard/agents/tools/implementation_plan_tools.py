"""Tools for managing structured implementation plans."""

import json
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles import AgentRoleType
from devboard.db.models.implementation_plan import ImplementationStepStatus, ImplementationStepType
from devboard.db.models.task import Task
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.task_git.service import TaskGitService
from devboard.services.task_implementation_plan import TaskImplementationPlanService


class StepInput(BaseModel):
    title: str
    type: Literal["code_change", "documentation", "validation", "code_review"]
    dependencies: list[int] = []
    details: str


# --- Planning Agent Tools ---


def create_set_implementation_plan_steps_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
) -> Tool:
    def set_implementation_plan_steps(
        steps: list[StepInput],
        overview: str | None = None,
    ) -> str:
        """Create or replace the structured implementation plan with discrete steps.

        Each step is a self-contained unit of work that can be executed by a sub-agent.
        Steps are automatically numbered from their position in the list (1-indexed).
        Dependencies reference step numbers (positions) of steps that must complete first.

        Args:
            steps: Ordered list of implementation steps. Each step has:
                - title: Short summary of the step
                - type: One of 'code_change', 'documentation', 'validation', 'code_review'
                - dependencies: List of step numbers (1-indexed positions) this step depends on
                - details: Detailed markdown instructions for execution
            overview: Optional brief summary of the implementation approach
        """
        if not steps:
            raise ModelRetry("At least one step is required")

        steps_data = [s.model_dump() for s in steps]
        try:
            plan_service.create_plan_with_steps(task.id, steps_data, overview)
        except ValueError as e:
            raise ModelRetry(f"Invalid dependency graph: {e}") from e
        plan_service.commit()

        return f"Implementation plan created with {len(steps)} steps."

    return Tool(
        function=set_implementation_plan_steps,
        name="set_implementation_plan_steps",
        requires_approval=False,
        takes_ctx=False,
    )


def create_add_implementation_step_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
) -> Tool:
    def add_implementation_step(
        title: str,
        type: Literal["code_change", "documentation", "validation", "code_review"],
        details: str,
        dependencies: list[int] | None = None,
    ) -> str:
        """Add a single step to the existing implementation plan.

        The step number is automatically assigned as max_existing + 1.

        Args:
            title: Short summary of the step
            type: One of 'code_change', 'documentation', 'validation', 'code_review'
            details: Detailed markdown instructions for execution
            dependencies: List of step numbers this step depends on (default: none)
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists. Use set_implementation_plan_steps first.")

        try:
            step = plan_service.add_step(plan, title=title, type=type, details=details, dependencies=dependencies)
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        plan_service.commit()
        return f"Step {step.step_number} '{title}' added to implementation plan."

    return Tool(
        function=add_implementation_step,
        name="add_implementation_step",
        requires_approval=False,
        takes_ctx=False,
    )


def create_edit_implementation_step_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
) -> Tool:
    def edit_implementation_step(
        step_number: int,
        title: str | None = None,
        type: Literal["code_change", "documentation", "validation", "code_review"] | None = None,
        dependencies: list[int] | None = None,
        details: str | None = None,
    ) -> str:
        """Edit a single step's fields by step number.

        Args:
            step_number: The step number to edit
            title: New title (unchanged if not provided)
            type: New type (unchanged if not provided)
            dependencies: New dependencies list (unchanged if not provided)
            details: New details (unchanged if not provided)
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists.")

        try:
            plan_service.update_step(
                plan, step_number, title=title, type=type, dependencies=dependencies, details=details
            )
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        plan_service.commit()
        return f"Step {step_number} updated."

    return Tool(
        function=edit_implementation_step,
        name="edit_implementation_step",
        requires_approval=False,
        takes_ctx=False,
    )


def create_remove_implementation_step_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
) -> Tool:
    def remove_implementation_step(step_number: int) -> str:
        """Remove a step from the implementation plan by step number.

        Fails if other steps depend on this step.

        Args:
            step_number: The step number to remove
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists.")

        try:
            plan_service.remove_step(plan, step_number)
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        plan_service.commit()
        return f"Step {step_number} removed."

    return Tool(
        function=remove_implementation_step,
        name="remove_implementation_step",
        requires_approval=False,
        takes_ctx=False,
    )


def create_edit_implementation_plan_overview_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
) -> Tool:
    def edit_implementation_plan_overview(overview: str) -> str:
        """Edit the implementation plan overview text.

        Args:
            overview: New overview text
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists.")

        plan_service.update_overview(plan, overview)
        plan_service.commit()
        return "Implementation plan overview updated."

    return Tool(
        function=edit_implementation_plan_overview,
        name="edit_implementation_plan_overview",
        requires_approval=False,
        takes_ctx=False,
    )


# --- Implementation (Coordination) Agent Tools ---


def create_execute_implementation_step_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_conversation_id: int | None,
    task_git_service: TaskGitService,
) -> Tool:
    async def execute_implementation_step(step_number: int) -> str:
        """Execute a specific implementation step by delegating to a step execution sub-agent.

        The step must be in 'pending' status and all its dependency steps must be 'complete'.
        The sub-agent will receive the step's details as instructions along with relevant context.

        Args:
            step_number: The step number to execute

        Returns:
            JSON string with the step execution outcome and conversation_id
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists for this task.")

        step = plan_service.get_step_by_number(plan, step_number)
        if not step:
            raise ModelRetry(f"Step {step_number} not found.")

        if step.status != ImplementationStepStatus.PENDING:
            raise ModelRetry(f"Step {step_number} is in '{step.status}' status, expected 'pending'.")

        # Check all dependencies are resolved (complete or skipped)
        resolved_statuses = {ImplementationStepStatus.COMPLETE, ImplementationStepStatus.SKIPPED}
        for dep_num in step.dependencies or []:
            dep_step = plan_service.get_step_by_number(plan, dep_num)
            if not dep_step or dep_step.status not in resolved_statuses:
                dep_status = dep_step.status if dep_step else "not found"
                raise ModelRetry(
                    f"Dependency step {dep_num} is not resolved (status: {dep_status}). "
                    f"Cannot execute step {step_number} until all dependencies are complete or skipped."
                )

        # Set step to running
        plan_service.set_step_status(plan, step_number, ImplementationStepStatus.RUNNING)
        plan_service.commit()

        try:
            from devboard.agents.tools.sub_agent_tools import run_sub_agent
            from devboard.db.models import ParentEntityType

            if step.type == ImplementationStepType.CODE_REVIEW:
                from devboard.agents.roles.code_review import CodeReviewAgentRole
                from devboard.agents.tools.sub_agent_tools import build_code_review_prompt

                diff = await task_git_service.get_task_all_changes(task)
                if not diff.files:
                    plan_service.set_step_status(
                        plan,
                        step_number,
                        ImplementationStepStatus.COMPLETE,
                        "No changes to review — the task diff is empty.",
                    )
                    plan_service.commit()
                    return json.dumps(
                        {"result": "No changes to review — the task diff is empty.", "conversation_id": None}
                    )

                role = CodeReviewAgentRole(task=task)
                prompt = build_code_review_prompt(diff, step.details or None)
                role_type = AgentRoleType.CODE_REVIEW
            else:
                from devboard.agents.roles.step_execution import StepExecutionAgentRole

                role = StepExecutionAgentRole(task=task, step=step)
                prompt = step.details
                role_type = AgentRoleType.STEP_EXECUTION

            sub_agent_result = await run_sub_agent(
                role=role,
                role_type=role_type,
                prompt=prompt,
                agent_config_service=agent_config_service,
                conversation_repo=conversation_repo,
                parent_entity_type=ParentEntityType.TASK,
                parent_entity_id=task.id,
                parent_conversation_id=parent_conversation_id,
            )

            # Update step status on success
            plan_service.set_step_status(plan, step_number, ImplementationStepStatus.COMPLETE, sub_agent_result.result)
            plan_service.commit()

            return json.dumps(
                {
                    "result": sub_agent_result.result,
                    "conversation_id": sub_agent_result.conversation_id,
                }
            )

        except Exception as e:
            # Update step status on failure
            plan_service.set_step_status(plan, step_number, ImplementationStepStatus.FAILED, str(e))
            plan_service.commit()

            return json.dumps(
                {
                    "result": f"Step {step_number} failed: {e}",
                    "conversation_id": None,
                }
            )

    return Tool(
        function=execute_implementation_step,
        name="execute_implementation_step",
    )
