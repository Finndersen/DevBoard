"""Tools for managing structured implementation plans."""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING, Literal

import logfire
from pydantic import BaseModel
from pydantic_ai import ModelRetry, Tool

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.events import SystemEvent, SystemEventType
from devboard.agents.exceptions import AgentInterruptedError
from devboard.agents.roles import AgentRoleType
from devboard.agents.roles.code_review import CodeReviewAgentRole
from devboard.agents.roles.step_execution import StepExecutionAgentRole
from devboard.agents.tools.sub_agent_tools import (
    build_code_review_prompt,
    create_sub_agent_conversation,
)
from devboard.api.schemas.document import DocumentEdit
from devboard.db.models.implementation_plan import ImplementationStepStatus, ImplementationStepType
from devboard.db.models.task import Task
from devboard.db.repositories.conversation import ConversationRepository
from devboard.services.task_git.service import TaskGitService
from devboard.services.task_implementation_plan import DependencyNotResolvedError, TaskImplementationPlanService

if TYPE_CHECKING:
    from devboard.agents.execution.manager import ConversationExecutionManager


class StepInput(BaseModel):
    title: str
    type: Literal["code_change", "documentation", "validation", "code_review"]
    model_type: Literal["fast", "standard", "advanced"] | None = None
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

        Use this tool both for initial plan creation AND for restructuring an existing plan
        (e.g. reordering steps, removing a step, inserting a step in the middle). It replaces
        the entire plan atomically, so pass the full desired set of steps each time.

        Args:
            steps: Ordered list of implementation steps. Each step has:
                - title: Short summary of the step
                - type: One of 'code_change', 'documentation', 'validation', 'code_review'
                - model_type: Model tier to use — 'fast' (Haiku), 'standard' (Sonnet), or 'advanced' (Opus).
                  Default for code_change/documentation/validation is 'fast'; code_review should use 'standard' or 'advanced'.
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
        function=set_implementation_plan_steps,  # ty:ignore[invalid-argument-type]
        name="set_implementation_plan_steps",
        requires_approval=False,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


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
        function=add_implementation_step,  # ty:ignore[invalid-argument-type]
        name="add_implementation_step",
        requires_approval=False,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


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
            raise ModelRetry("No implementation plan exists yet. Use `set_implementation_plan_steps` first.")

        try:
            plan_service.update_step(
                plan, step_number, title=title, type=type, dependencies=dependencies, details=details
            )
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        plan_service.commit()
        return f"Step {step_number} updated."

    return Tool(
        function=edit_implementation_step,  # ty:ignore[invalid-argument-type]
        name="edit_implementation_step",
        requires_approval=False,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


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
            raise ModelRetry("No implementation plan exists yet. Use `set_implementation_plan_steps` first.")

        plan_service.update_overview(plan, overview)
        plan_service.commit()
        return "Implementation plan overview updated."

    return Tool(
        function=edit_implementation_plan_overview,  # ty:ignore[invalid-argument-type]
        name="edit_implementation_plan_overview",
        requires_approval=False,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


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
            raise ModelRetry("No implementation plan exists yet. Use `set_implementation_plan_steps` first.")

        step = plan_service.get_step_by_number(plan, step_number)
        if not step:
            raise ModelRetry(f"Step {step_number} not found.")

        return step.details

    return Tool(
        function=read_implementation_step_details,  # ty:ignore[invalid-argument-type]
        name="read_implementation_step_details",
        requires_approval=False,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


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
            raise ModelRetry("No implementation plan exists yet. Use `set_implementation_plan_steps` first.")

        try:
            plan_service.edit_step_details(plan, step_number, edits)
        except ValueError as e:
            raise ModelRetry(str(e)) from e
        plan_service.commit()
        return f"Step {step_number} details updated."

    return Tool(
        function=edit_implementation_step_details,  # ty:ignore[invalid-argument-type]
        name="edit_implementation_step_details",
        requires_approval=False,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


def create_get_implementation_plan_overview_tool(
    task: Task,
) -> Tool:
    def get_implementation_plan_overview() -> str:
        """Get a lightweight overview of the current implementation plan.

        Returns all steps with step number, title, type, status, and dependencies.
        Includes conversation IDs for steps that have been started.
        Use this to check current plan state (e.g. which steps are complete/running/pending)
        since step statuses are not included in the initial context snapshot.
        Conversation IDs can be used with the inspect_conversation tool to analyse step progress.
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists for this task.")

        lines = []
        if plan.overview:
            lines.append(f"Overview: {plan.overview}\n")
        lines.append("Steps:")
        for step in plan.steps:
            deps = f" (depends on: {', '.join(str(d) for d in step.dependencies)})" if step.dependencies else ""
            conv_id = f" conv_id={step.conversation_id}" if step.conversation_id is not None else ""
            lines.append(f"  {step.step_number}. [{step.status}] {step.title} [{step.type}]{deps}{conv_id}")

        return "\n".join(lines)

    return Tool(
        function=get_implementation_plan_overview,  # ty:ignore[invalid-argument-type]
        name="get_implementation_plan_overview",
        requires_approval=False,
        takes_ctx=False,
    )  # ty:ignore[invalid-return-type]


# --- Implementation (Coordination) Agent Tools ---


def create_execute_implementation_step_tool(
    task: Task,
    plan_service: TaskImplementationPlanService,
    agent_config_service: AgentConfigService,
    conversation_repo: ConversationRepository,
    parent_conversation_id: int | None,
    working_dir: str,
    execution_manager: ConversationExecutionManager,
    task_git_service: TaskGitService | None = None,
) -> Tool:
    async def execute_implementation_step(
        step_number: int,
        force_run: bool = False,
        notes: str | None = None,
    ) -> str:
        """Execute a specific implementation step by delegating to a step execution sub-agent.

        The step must be in 'pending', 'running' (if no active execution), 'failed', or 'interrupted' status
        and all its dependency steps must be 'complete'. Failed, interrupted, or stale-running steps resume
        the existing conversation so the sub-agent retains full prior context. Use `notes` to describe
        what has changed since the last run or what to do differently.

        Args:
            step_number: The step number to execute
            force_run: If True, skip status and dependency validation. Use to recover plans stuck
                in an inconsistent state (e.g. step left in 'running' after a crash), bypass a
                failed dependency, or re-run a 'complete' step (e.g. soft failure where the agent
                reported it could not complete, or re-doing a code review after making changes).
            notes: Optional guidance for the execution agent. When re-running a step, describe
                what has changed since the last attempt or what to do differently.

        Returns:
            JSON string with the step execution outcome and conversation_id
        """
        plan = task.implementation_plan_structured
        if not plan:
            raise ModelRetry("No implementation plan exists for this task.")

        step = plan_service.get_step_by_number(plan, step_number)
        if not step:
            raise ModelRetry(f"Step {step_number} not found.")

        # Guard: reject steps in RUNNING status if they have active execution,
        # even with force_run=True, to prevent running the same step twice.
        if step.status == ImplementationStepStatus.RUNNING and step.conversation_id is not None:
            if execution_manager.has_active_execution(step.conversation_id):
                raise ModelRetry(f"Step {step_number} is already running.")

        if not force_run:
            # INTERRUPTED steps can be re-executed like FAILED steps — they resume the
            # existing conversation so the sub-agent retains full prior context.
            # RUNNING steps with no active execution can also be re-executed (stale RUNNING status).
            EXECUTABLE_STATUSES = {
                ImplementationStepStatus.PENDING,
                ImplementationStepStatus.RUNNING,
                ImplementationStepStatus.FAILED,
                ImplementationStepStatus.INTERRUPTED,
            }
            if step.status not in EXECUTABLE_STATUSES:
                raise ModelRetry(
                    f"Step {step_number} is in '{step.status}' status, expected 'pending', 'running', 'failed', or 'interrupted'."
                )
            try:
                plan_service.check_dependencies_resolved(plan, step)
            except DependencyNotResolvedError as e:
                raise ModelRetry(str(e)) from e

        plan_service.set_step_status(step, status=ImplementationStepStatus.RUNNING)

        try:
            role_type = (
                AgentRoleType.CODE_REVIEW
                if step.type == ImplementationStepType.CODE_REVIEW
                else AgentRoleType.STEP_EXECUTION
            )

            # --- Conversation handling ---
            if step.conversation_id is not None:
                resuming = True
                conversation = conversation_repo.get_by_id(step.conversation_id)
                if conversation is None:
                    raise ValueError(f"Conversation {step.conversation_id} for step {step_number} not found.")
            else:
                resuming = False
                step_model_type = step.model_type
                conversation = create_sub_agent_conversation(
                    role_type=role_type,
                    agent_config_service=agent_config_service,
                    conversation_repo=conversation_repo,
                    parent_entity=task,
                    parent_conversation_id=parent_conversation_id,
                    model_type=step_model_type,
                )
                plan_service.set_step_conversation(step, conversation.id)

            # Notify the frontend immediately so Cancel and sub-agent buttons appear
            if parent_conversation_id is not None:
                await execution_manager.broadcast_event(
                    parent_conversation_id,
                    SystemEvent(
                        sub_type=SystemEventType.IMPLEMENTATION_STEP_STARTED,
                        data={
                            "task_id": task.id,
                            "step_number": step_number,
                            "conversation_id": conversation.id,
                        },
                        timestamp=datetime.datetime.now(datetime.UTC),
                    ),
                )

            # --- Agent role ---
            if step.type == ImplementationStepType.CODE_REVIEW:
                role = CodeReviewAgentRole(task=task, working_dir=working_dir)
            else:
                role = StepExecutionAgentRole(task=task, step=step, working_dir=working_dir)

            # --- Prompt ---
            if resuming:
                prompt = "Resume and complete the step."
                if notes:
                    prompt += f"\n\n## Coordinator Notes\n\n{notes}"
            elif step.type == ImplementationStepType.CODE_REVIEW:
                diff = await (task_git_service or TaskGitService).get_task_all_changes(task)
                if not diff.files:
                    plan_service.set_step_status(
                        step,
                        status=ImplementationStepStatus.COMPLETE,
                        outcome="No changes to review — the task diff is empty.",
                    )
                    return json.dumps(
                        {
                            "result": "No changes to review — the task diff is empty.",
                            "conversation_id": None,
                            "step_type": step.type,
                        }
                    )
                additional_context = "\n\n".join(filter(None, [step.details or None, notes]))
                prompt = build_code_review_prompt(diff=diff, additional_context=additional_context or None)
            else:
                prompt = f"## Current Step {step.step_number}: {step.title}\n\n{step.details}"
                if notes:
                    prompt += f"\n\n## Coordinator Notes\n\n{notes}"

            sub_agent_result = await execution_manager.run_sub_agent_execution(
                conversation=conversation,
                role=role,
                prompt=prompt,
                conversation_repo=conversation_repo,
                agent_config_service=agent_config_service,
                working_dir=working_dir,
            )

            plan_service.set_step_status(
                step, status=ImplementationStepStatus.COMPLETE, outcome=sub_agent_result.result
            )

            return json.dumps(
                {
                    "result": sub_agent_result.result,
                    "conversation_id": sub_agent_result.conversation_id,
                    "step_type": step.type,
                }
            )

        except AgentInterruptedError:
            plan_service.set_step_status(
                step, status=ImplementationStepStatus.INTERRUPTED, outcome="Step interrupted by user."
            )
            logfire.info(f"Step {step_number} interrupted — propagating AgentInterruptedError to parent execution")
            raise
        except Exception as e:
            plan_service.set_step_status(step, status=ImplementationStepStatus.FAILED, outcome=str(e))
            raise ModelRetry(f"Step {step_number} failed: {e}") from e

    return Tool(
        function=execute_implementation_step,  # ty:ignore[invalid-argument-type]
        name="execute_implementation_step",
    )  # ty:ignore[invalid-return-type]
