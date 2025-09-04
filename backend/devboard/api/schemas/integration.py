"""Integration schemas for API responses."""

from pydantic import BaseModel


class IntegrationTestResponse(BaseModel):
    """Response schema for integration connection test."""

    integration_type: str
    success: bool
    error_message: str | None = None
    error_type: str | None = None


class ModelInfo(BaseModel):
    """Schema for individual model information."""

    id: str
    provider: str
    name: str


class AgentModelInfo(BaseModel):
    """Schema for agent-specific model information."""

    available_models: list[ModelInfo]
    preferred_model: str | None = None
    total_available: int


class AvailableModelsResponse(BaseModel):
    """Response schema for available models endpoint."""

    agent_type: str | None = None
    qa: AgentModelInfo | None = None
    planning: AgentModelInfo | None = None
    implementation: AgentModelInfo | None = None
    available_models: list[ModelInfo] | None = None
    preferred_model: str | None = None
    total_available: int | None = None
