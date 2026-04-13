"""Repository for implementation plan and step data access operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from devboard.db.models.implementation_plan import (
    ImplementationPlan,
    ImplementationStep,
    ImplementationStepStatus,
    ImplementationStepType,
)
from devboard.db.repositories.base import BaseRepository


class TaskImplementationPlanRepository(BaseRepository[ImplementationPlan]):
    def create(self, task_id: int, overview: str | None = None) -> ImplementationPlan:
        plan = ImplementationPlan(task_id=task_id, overview=overview)
        self.db.add(plan)
        self.db.flush()
        return plan

    def get_by_task_id(self, task_id: int) -> ImplementationPlan | None:
        stmt = (
            select(ImplementationPlan)
            .where(ImplementationPlan.task_id == task_id)
            .options(joinedload(ImplementationPlan.steps))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_by_id(self, plan_id: int) -> ImplementationPlan | None:
        stmt = (
            select(ImplementationPlan)
            .where(ImplementationPlan.id == plan_id)
            .options(joinedload(ImplementationPlan.steps))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def update(self, plan: ImplementationPlan) -> ImplementationPlan:
        self.db.flush()
        return plan

    def delete_by_task_id(self, task_id: int) -> None:
        plan = self.get_by_task_id(task_id)
        if plan:
            self.db.delete(plan)
            self.db.flush()

    def create_steps(self, plan_id: int, steps_data: list[dict[str, Any]]) -> list[ImplementationStep]:
        steps: list[ImplementationStep] = []
        for idx, step_data in enumerate(steps_data, start=1):
            step = ImplementationStep(
                implementation_plan_id=plan_id,
                step_number=idx,
                title=step_data["title"],
                type=ImplementationStepType(step_data["type"]),
                dependencies=step_data.get("dependencies", []),
                status=ImplementationStepStatus.PENDING,
                details=step_data["details"],
            )
            self.db.add(step)
            steps.append(step)
        self.db.flush()
        return steps

    def get_max_step_number(self, plan_id: int) -> int | None:
        """Return the highest step_number in the plan, or None if no steps exist."""
        stmt = select(func.max(ImplementationStep.step_number)).where(
            ImplementationStep.implementation_plan_id == plan_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_step_by_number(self, plan_id: int, step_number: int) -> ImplementationStep | None:
        stmt = select(ImplementationStep).where(
            ImplementationStep.implementation_plan_id == plan_id,
            ImplementationStep.step_number == step_number,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update_step(self, step: ImplementationStep) -> ImplementationStep:
        self.db.flush()
        return step

    def delete_step(self, step: ImplementationStep, plan: ImplementationPlan) -> None:
        # Check no other steps depend on this step
        for other_step in plan.steps:
            if other_step.id != step.id and step.step_number in (other_step.dependencies or []):
                raise ValueError(f"Cannot delete step {step.step_number}: step {other_step.step_number} depends on it")
        self.db.delete(step)
        self.db.flush()
