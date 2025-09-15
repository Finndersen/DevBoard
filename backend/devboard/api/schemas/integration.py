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


class AgentModelResponse(BaseModel):
    """Response schema for agent model endpoint."""

    model_id: str


class AvailableModelsResponse(BaseModel):
    """Response schema for available models endpoint."""

    agent_type: str
    available_models: list[ModelInfo]
    preferred_model: str | None = None
    total_available: int
    model_hierarchy: list[str] | None = None  # Default fallback hierarchy for this agent


class UpdateAgentModelRequest(BaseModel):
    """Request schema for updating agent model selection."""

    model_id: str | None = None  # None means use default hierarchy
