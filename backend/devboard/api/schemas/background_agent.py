"""Schemas for background agents and background agent runs."""

import datetime
from typing import Any

from pydantic import BaseModel

from devboard.agents.engines import AgentEngine
from devboard.db.models.background_agent_run import BackgroundAgentRunStatus


class BackgroundAgentEventTriggerCreate(BaseModel):
    """Schema for creating an event trigger."""

    event_type_pattern: str


class BackgroundAgentScheduleTriggerCreate(BaseModel):
    """Schema for creating a schedule trigger."""

    cron_expression: str


class BackgroundAgentEventTriggerResponse(BaseModel):
    """Response schema for an event trigger."""

    id: int
    agent_id: int
    event_type_pattern: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class BackgroundAgentScheduleTriggerResponse(BaseModel):
    """Response schema for a schedule trigger."""

    id: int
    agent_id: int
    cron_expression: str
    last_triggered_at: datetime.datetime | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class BackgroundAgentCreate(BaseModel):
    """Schema for creating a new background agent."""

    name: str
    prompt: str
    engine: AgentEngine
    description: str | None = None
    model_id: str | None = None
    enabled: bool = True
    project_id: int | None = None
    mcp_tool_ids: list[int] = []
    event_triggers: list[BackgroundAgentEventTriggerCreate] = []
    schedule_triggers: list[BackgroundAgentScheduleTriggerCreate] = []


class BackgroundAgentUpdate(BaseModel):
    """Schema for updating a background agent."""

    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    engine: AgentEngine | None = None
    model_id: str | None = None
    enabled: bool | None = None
    project_id: int | None = None
    mcp_tool_ids: list[int] | None = None
    event_triggers: list[BackgroundAgentEventTriggerCreate] | None = None
    schedule_triggers: list[BackgroundAgentScheduleTriggerCreate] | None = None


class BackgroundAgentResponse(BaseModel):
    """Response schema for a background agent."""

    id: int
    name: str
    description: str | None
    prompt: str
    engine: AgentEngine
    model_id: str | None
    state: dict[str, Any]
    enabled: bool
    project_id: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    mcp_tool_ids: list[int]
    event_triggers: list[BackgroundAgentEventTriggerResponse]
    schedule_triggers: list[BackgroundAgentScheduleTriggerResponse]

    model_config = {"from_attributes": True}


class BackgroundAgentStateUpdate(BaseModel):
    """Schema for partially merging background agent state."""

    state: dict[str, Any]


class BackgroundAgentRunResponse(BaseModel):
    """Response schema for a background agent run record."""

    id: int
    agent_id: int
    conversation_id: int
    triggered_by: str
    trigger_event_id: str | None
    started_at: datetime.datetime
    completed_at: datetime.datetime | None
    status: BackgroundAgentRunStatus
    state_before: dict[str, Any]
    state_after: dict[str, Any] | None
    input_tokens: int | None
    output_tokens: int | None
    error: str | None

    model_config = {"from_attributes": True}


class BackgroundAgentRunStatsResponse(BaseModel):
    """Aggregate statistics for a background agent's runs."""

    total_runs: int
    completed: int
    failed: int
    avg_input_tokens: float | None
    avg_output_tokens: float | None


class ManualTriggerResponse(BaseModel):
    """Response for manual trigger endpoint."""

    conversation_id: int
