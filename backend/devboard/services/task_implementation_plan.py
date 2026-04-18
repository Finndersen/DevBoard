"""Service for managing structured implementation plans."""

import datetime
from collections import defaultdict
from typing import Any

from devboard.agents.language_models import ModelType
from devboard.api.schemas.document import DocumentEdit
from devboard.db.models.implementation_plan import (
    ImplementationPlan,
    ImplementationStep,
    ImplementationStepStatus,
    ImplementationStepType,
)
from devboard.db.repositories.implementation_plan import TaskImplementationPlanRepository
from devboard.services.document_editor import DocumentEditorService


class DependencyNotResolvedError(Exception):
    """Raised when a step's dependencies have not been resolved."""


class TaskImplementationPlanService:
    """Business logic for task implementation plans."""

    def __init__(self, plan_repo: TaskImplementationPlanRepository):
        self.plan_repo = plan_repo

    def get_plan_by_task_id(self, task_id: int) -> ImplementationPlan | None:
        return self.plan_repo.get_by_task_id(task_id)

    def create_plan_with_steps(
        self,
        task_id: int,
        steps_data: list[dict[str, Any]],
        overview: str | None = None,
    ) -> ImplementationPlan:
        """Create or replace a plan with steps. Validates dependency graph first."""
        self.validate_dependency_graph(steps_data)

        # Delete existing plan if present (replacement semantics)
        self.plan_repo.delete_by_task_id(task_id)

        plan = self.plan_repo.create(task_id=task_id, overview=overview)
        self.plan_repo.create_steps(plan.id, steps_data)
        return plan

    def add_step(
        self,
        plan: ImplementationPlan,
        title: str,
        type: str,
        details: str,
        dependencies: list[int] | None = None,
        model_type: str | None = None,
    ) -> ImplementationStep:
        """Add a single step to an existing plan."""
        deps = dependencies or []
        existing_numbers = {s.step_number for s in plan.steps}
        for dep in deps:
            if dep not in existing_numbers:
                raise ValueError(f"Dependency step {dep} does not exist")

        # Query the DB directly rather than relying on the in-memory relationship,
        # which may be stale if add_step is called multiple times in the same session.
        max_number = self.plan_repo.get_max_step_number(plan.id)
        new_number = (max_number or 0) + 1

        step = ImplementationStep(
            implementation_plan_id=plan.id,
            step_number=new_number,
            title=title,
            type=ImplementationStepType(type),
            dependencies=deps,
            status=ImplementationStepStatus.PENDING,
            details=details,
            model_type=ModelType(model_type) if model_type else None,
        )
        self.plan_repo.db.add(step)
        self.plan_repo.db.flush()
        return step

    def update_step(
        self,
        plan: ImplementationPlan,
        step_number: int,
        title: str | None = None,
        type: str | None = None,
        dependencies: list[int] | None = None,
        details: str | None = None,
        model_type: str | None = None,
    ) -> ImplementationStep:
        """Update a step's fields. Validates dependency changes including cycle detection."""
        step = self.plan_repo.get_step_by_number(plan.id, step_number)
        if not step:
            raise ValueError(f"Step {step_number} not found")

        if title is not None:
            step.title = title
        if type is not None:
            step.type = ImplementationStepType(type)
        if dependencies is not None:
            # Build full graph with proposed change and validate
            steps_data = [
                {"dependencies": dependencies if s.step_number == step_number else (s.dependencies or [])}
                for s in sorted(plan.steps, key=lambda s: s.step_number)
            ]
            self.validate_dependency_graph(steps_data)
            step.dependencies = dependencies
        if details is not None:
            step.details = details
        if model_type is not None:
            step.model_type = ModelType(model_type)

        self.plan_repo.update_step(step)
        return step

    def remove_step(self, plan: ImplementationPlan, step_number: int) -> None:
        """Remove a step. Validates no other steps depend on it."""
        step = self.plan_repo.get_step_by_number(plan.id, step_number)
        if not step:
            raise ValueError(f"Step {step_number} not found")
        self.plan_repo.delete_step(step, plan)

    def update_overview(self, plan: ImplementationPlan, overview: str) -> None:
        """Update the plan overview text."""
        plan.overview = overview
        self.plan_repo.update(plan)

    def set_step_status(
        self,
        step: ImplementationStep,
        status: ImplementationStepStatus,
        outcome: str | None = None,
    ) -> ImplementationStep:
        """Update a step's execution status and optional outcome, then commit."""
        step.status = status
        if outcome is not None:
            step.outcome = outcome
        if status == ImplementationStepStatus.RUNNING:
            step.started_at = datetime.datetime.now(datetime.UTC)
        elif status in (
            ImplementationStepStatus.COMPLETE,
            ImplementationStepStatus.FAILED,
            ImplementationStepStatus.SKIPPED,
        ):
            step.completed_at = datetime.datetime.now(datetime.UTC)
        self.plan_repo.update_step(step)
        self.plan_repo.commit()
        return step

    def set_step_conversation(self, step: ImplementationStep, conversation_id: int) -> None:
        """Set the conversation ID for a step and commit."""
        step.conversation_id = conversation_id
        self.plan_repo.update_step(step)
        self.plan_repo.commit()

    def check_dependencies_resolved(self, plan: ImplementationPlan, step: ImplementationStep) -> None:
        """Validate all dependency steps are complete or skipped.

        Raises:
            DependencyNotResolvedError: If any dependency is not resolved.
        """
        resolved_statuses = {ImplementationStepStatus.COMPLETE, ImplementationStepStatus.SKIPPED}
        steps_by_number = {s.step_number: s for s in plan.steps}
        for dep_num in step.dependencies or []:
            dep_step = steps_by_number.get(dep_num)
            if not dep_step or dep_step.status not in resolved_statuses:
                dep_status = dep_step.status if dep_step else "not found"
                raise DependencyNotResolvedError(
                    f"Dependency step {dep_num} is not resolved (status: {dep_status}). "
                    f"Cannot execute step {step.step_number} until all dependencies are complete or skipped."
                )

    def edit_step_details(
        self,
        plan: ImplementationPlan,
        step_number: int,
        edits: list[DocumentEdit],
    ) -> ImplementationStep:
        step = self.plan_repo.get_step_by_number(plan.id, step_number)
        if not step:
            raise ValueError(f"Step {step_number} not found")
        if not step.details:
            raise ValueError(f"Step {step_number} has no details to edit")

        result = DocumentEditorService().apply_edits(step.details, edits)
        if not result.success:
            raise ValueError(f"Failed to apply edits: {'; '.join(result.errors)}")

        step.details = result.content
        self.plan_repo.update_step(step)
        return step

    def get_step_by_number(self, plan: ImplementationPlan, step_number: int) -> ImplementationStep | None:
        return self.plan_repo.get_step_by_number(plan.id, step_number)

    def commit(self) -> None:
        self.plan_repo.commit()

    @staticmethod
    def validate_dependency_graph(steps_data: list[dict[str, Any]]) -> None:
        """Validate that the dependency graph has no cycles and no invalid references.

        Raises:
            ValueError: If cycles or invalid references are found
        """
        step_numbers = set(range(1, len(steps_data) + 1))

        # Check for invalid references
        for idx, step_data in enumerate(steps_data, start=1):
            deps = step_data.get("dependencies", [])
            for dep in deps:
                if dep not in step_numbers:
                    raise ValueError(f"Step {idx} references non-existent step {dep}")
                if dep == idx:
                    raise ValueError(f"Step {idx} cannot depend on itself")

        # Topological sort to detect cycles
        graph: dict[int, list[int]] = defaultdict(list)
        in_degree: dict[int, int] = dict.fromkeys(step_numbers, 0)

        for idx, step_data in enumerate(steps_data, start=1):
            for dep in step_data.get("dependencies", []):
                graph[dep].append(idx)
                in_degree[idx] += 1

        queue = [n for n in step_numbers if in_degree[n] == 0]
        visited_count = 0

        while queue:
            node = queue.pop(0)
            visited_count += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(step_numbers):
            raise ValueError("Dependency graph contains a cycle")
