"""Implementation plan and step database models."""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .task import Task


class ImplementationStepType(StrEnum):
    CODE_CHANGE = "code_change"
    DOCUMENTATION = "documentation"
    VALIDATION = "validation"
    CODE_REVIEW = "code_review"


class ImplementationStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


class ImplementationPlan(Base):
    """Structured implementation plan for a task, containing discrete steps."""

    __tablename__ = "implementation_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), unique=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    task: Mapped["Task"] = relationship(back_populates="implementation_plan_structured")
    steps: Mapped[list["ImplementationStep"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ImplementationStep.step_number",
    )

    @property
    def status(self) -> str:
        """Compute plan status from step statuses."""
        if not self.steps:
            return "pending"
        statuses = {s.status for s in self.steps}
        if ImplementationStepStatus.FAILED in statuses:
            return "failed"
        if all(s in (ImplementationStepStatus.COMPLETE, ImplementationStepStatus.SKIPPED) for s in statuses):
            return "complete"
        if statuses & {ImplementationStepStatus.RUNNING, ImplementationStepStatus.COMPLETE}:
            return "executing"
        return "pending"


class ImplementationStep(Base):
    """A discrete step within an implementation plan."""

    __tablename__ = "implementation_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    implementation_plan_id: Mapped[int] = mapped_column(ForeignKey("implementation_plans.id", ondelete="CASCADE"))
    step_number: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(500))
    type: Mapped[ImplementationStepType] = mapped_column(Enum(ImplementationStepType))
    dependencies: Mapped[list[int]] = mapped_column(JSON, default=list)
    status: Mapped[ImplementationStepStatus] = mapped_column(
        Enum(ImplementationStepStatus), default=ImplementationStepStatus.PENDING
    )
    details: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True, default=None)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.UTC),
        onupdate=lambda: datetime.datetime.now(datetime.UTC),
    )

    plan: Mapped["ImplementationPlan"] = relationship(back_populates="steps")
