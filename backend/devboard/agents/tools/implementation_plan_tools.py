"""Tools for managing structured implementation plans."""

import json
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.roles import AgentRoleType
from devboard.agents.roles.code_review import CodeReviewAgentRole
from devboard.agents.roles.step_execution import StepExecutionAgentRole
from devboard.agents.tools.sub_agent_tools import build_code_review_prompt, run_sub_agent
from devboard.api.schemas.document import DocumentEdit
from devboard.db.models import ParentEntityType
from devboard.db.models.implementation_plan import ImplementationStepStatus, ImplementationStepType
from devboard.db.models.task import Task
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.task_git.service import TaskGitService
from devboard.services.task_implementation_plan import DependencyNotResolvedError, TaskImplementationPlanService


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
            plan_service.create_plan_with_steps(task_id=task.id, steps_data=steps_data, overview=overview)
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


def create_read_implementation_step_details_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
) -> Tool:
    def read_implementation_step_details(step_number: int) -> str:
        """Read the full details/instructions of a specific implementation plan step.

        Args:
            step_number: The step number to read details for
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists.")

        step = plan_service.get_step_by_number(plan, step_number)
        if not step:
            raise ModelRetry(f"Step {step_number} not found.")

        return step.details

    return Tool(
        function=read_implementation_step_details,
        name="read_implementation_step_details",
        requires_approval=False,
        takes_ctx=False,
    )


def create_edit_implementation_step_details_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
) -> Tool:
    def edit_implementation_step_details(step_number: int, edits: list[DocumentEdit]) -> str:
        """Apply targeted find-replace edits to a step's details field.

        Use this instead of edit_implementation_step when making small or partial
        changes to a step's details — avoids re-transmitting the entire content.

        Args:
            step_number: The step number to edit
            edits: List of find-replace edits. Each edit has:
                - old_string: Exact text to find (must be unique within the details)
                - new_string: Replacement text
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists.")

        try:
            plan_service.edit_step_details(plan, step_number, edits)
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        plan_service.commit()
        return f"Step {step_number} details updated."

    return Tool(
        function=edit_implementation_step_details,
        name="edit_implementation_step_details",
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
    working_dir: str,
) -> Tool:
    async def execute_implementation_step(
        step_number: int,
        force_run: bool = False,
        notes: str | None = None,
    ) -> str:
        """Execute a specific implementation step by delegating to a step execution sub-agent.

        The step must be in 'pending' or 'failed' status and all its dependency steps must be 'complete'.
        Failed steps can be retried by calling this tool again.
        The sub-agent will receive the step's details as instructions along with relevant context.

        Args:
            step_number: The step number to execute
            force_run: If True, skip status and dependency validation. Use only to
                recover plans stuck in an inconsistent state (e.g. step left in
                'running' after a crash, or a failed dependency you want to bypass).
            notes: Optional context/notes to provide to the execution agent — e.g. a
                change in approach or considerations based on outcomes of previous steps.
                Appended to the sub-agent prompt.

        Returns:
            JSON string with the step execution outcome and conversation_id
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists for this task.")

        step = plan_service.get_step_by_number(plan, step_number)
        if not step:
            raise ModelRetry(f"Step {step_number} not found.")

        if not force_run:
            EXECUTABLE_STATUSES = {ImplementationStepStatus.PENDING, ImplementationStepStatus.FAILED}
            if step.status not in EXECUTABLE_STATUSES:
                raise ModelRetry(f"Step {step_number} is in '{step.status}' status, expected 'pending' or 'failed'.")
            try:
                plan_service.check_dependencies_resolved(plan, step)
            except DependencyNotResolvedError as e:
                raise ModelRetry(str(e)) from e

        plan_service.set_step_status(step, ImplementationStepStatus.RUNNING)

        try:
            if step.type == ImplementationStepType.CODE_REVIEW:
                diff = await TaskGitService.get_task_all_changes(task)
                if not diff.files:
                    plan_service.set_step_status(
                        step,
                        ImplementationStepStatus.COMPLETE,
                        "No changes to review — the task diff is empty.",
                    )
                    return json.dumps(
                        {
                            "result": "No changes to review — the task diff is empty.",
                            "conversation_id": None,
                            "step_type": step.type,
                        }
                    )

                role = CodeReviewAgentRole(task=task, working_dir=working_dir)
                additional_context = "\n\n".join(filter(None, [step.details or None, notes]))
                prompt = build_code_review_prompt(diff=diff, additional_context=additional_context or None)
                role_type = AgentRoleType.CODE_REVIEW
            else:
                role = StepExecutionAgentRole(task=task, step=step, working_dir=working_dir)
                prompt = f"## Step {step.step_number}: {step.title}\n\n{step.details}"
                if notes:
                    prompt += f"\n\n## Coordinator Notes\n\n{notes}"
                role_type = AgentRoleType.STEP_EXECUTION

            sub_agent_result = await run_sub_agent(
                role=role,
                role_type=role_type,
                prompt=prompt,
                agent_config_service=agent_config_service,
                conversation_repo=conversation_repo,
                parent_entity_type=ParentEntityType.TASK,
                parent_entity_id=task.id,
                working_dir=working_dir,
                parent_conversation_id=parent_conversation_id,
            )

            plan_service.set_step_status(step, ImplementationStepStatus.COMPLETE, sub_agent_result.result)

            return json.dumps(
                {
                    "result": sub_agent_result.result,
                    "conversation_id": sub_agent_result.conversation_id,
                    "step_type": step.type,
                }
            )

        except Exception as e:
            plan_service.set_step_status(step, ImplementationStepStatus.FAILED, str(e))
            raise ModelRetry(f"Step {step_number} failed: {e}") from e

    return Tool(
        function=execute_implementation_step,
        name="execute_implementation_step",
    )
