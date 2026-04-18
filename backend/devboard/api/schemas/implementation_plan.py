"""Implementation plan API schemas."""

import datetime

from pydantic import BaseModel


class ImplementationStepResponse(BaseModel):
    id: int
    step_number: int
    title: str
    type: str
    dependencies: list[int]
    status: str
    details: str
    outcome: str | None
    model_type: str | None
    model_display_name: str | None
    conversation_id: int | None
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class ImplementationPlanResponse(BaseModel):
    id: int
    task_id: int
    overview: str | None
    status: str
    steps: list[ImplementationStepResponse]

    model_config = {"from_attributes": True}


class ImplementationStepUpdate(BaseModel):
    title: str | None = None
    type: str | None = None
    dependencies: list[int] | None = None
    details: str | None = None
    model_type: str | None = None


class ImplementationStepCreate(BaseModel):
    title: str
    type: str
    details: str
    dependencies: list[int] = []
    model_type: str | None = None
