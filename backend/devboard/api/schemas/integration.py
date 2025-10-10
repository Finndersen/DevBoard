"""Integration schemas for API responses."""

from pydantic import BaseModel

from devboard.agents.types import ModelInfo


class IntegrationTestResponse(BaseModel):
    """Response schema for integration connection test."""

    integration_type: str
    success: bool
    error_message: str | None = None
    error_type: str | None = None


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


class UpdateAgentModelRequest(BaseModel):
    """Request schema for updating agent model selection."""

    model_id: str | None = None  # None means use default hierarchy


class AgentEngineInfo(BaseModel):
    """Information about an available agent engine."""

    engine: str
    display_name: str
    description: str


class AgentEngineModelConfigSchema(BaseModel):
    """Combined engine and model configuration."""

    engine: str
    model_id: str


class AgentConfigurationResponse(BaseModel):
    """Response for agent configuration endpoints."""

    agent_role: str
    config: AgentEngineModelConfigSchema
    available_engines: list[AgentEngineInfo]


class UpdateAgentConfigurationRequest(BaseModel):
    """Request to update agent configuration."""

    engine: str
    model_id: str


class AvailableModelsByEngineResponse(BaseModel):
    """Response with models grouped by engine."""

    models_by_engine: dict[str, list[ModelInfo]]


class UpdateConversationModelRequest(BaseModel):
    """Request to update conversation model."""

    model_id: str
