"""Agents API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.agent_config_service import (
    AgentConfigService,
    AgentConfiguration,
    AgentEngineModelConfig,
    AvailableModelsByEngine,
)
from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.roles.types import (
    AgentRole,
)
from devboard.api.dependencies.services import get_agent_config_service
from devboard.api.schemas import UpdateAgentConfigurationRequest

router = APIRouter()


@router.get("/{agent_role}/configuration", response_model=AgentConfiguration)
async def get_agent_configuration(
    agent_role: str,
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentConfiguration:
    """Get configuration for an agent role.

    Returns the effective engine and model configuration, along with
    available engines for the role.

    Args:
        agent_role: Agent role (project, task_specification, task_planning, task_implementation, investigation)
        service: Agent configuration service

    Returns:
        Agent configuration with effective values and available options
    """
    try:
        role = AgentRole(agent_role)
    except ValueError:
        valid_roles = [r.value for r in AgentRole]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent role: {agent_role}. Must be one of: {', '.join(valid_roles)}",
        ) from None

    return service.get_agent_configuration(role)


@router.put("/{agent_role}/configuration", response_model=AgentConfiguration)
async def update_agent_configuration(
    agent_role: str,
    request: UpdateAgentConfigurationRequest,
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentConfiguration:
    """Update configuration for an agent role.

    Updates both engine and model for the role. Validates that:
    - Engine is allowed for the role
    - Model is available for the engine (provider configured)

    Args:
        agent_role: Agent role to update
        request: New engine and model configuration
        service: Agent configuration service

    Returns:
        Updated agent configuration

    Raises:
        HTTPException: 400 if validation fails
    """
    try:
        role = AgentRole(agent_role)
        config = AgentEngineModelConfig(
            engine=AgentEngine(request.engine),
            model_id=request.model_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    try:
        return service.update_agent_configuration(role, config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/available-models", response_model=AvailableModelsByEngine)
async def get_available_models_by_engine(
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AvailableModelsByEngine:
    """Get all available models grouped by engine.

    Returns models from all configured providers, organized by which
    engine supports them.

    Args:
        service: Agent configuration service

    Returns:
        Models grouped by engine name
    """
    return service.get_available_models_by_engine()
