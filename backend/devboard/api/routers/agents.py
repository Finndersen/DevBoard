"""Agents API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.llm_service import LLMService
from devboard.agents.types import AgentType
from devboard.api.dependencies.services import get_llm_service
from devboard.api.schemas import (
    AgentModelResponse,
    AvailableModelsResponse,
    UpdateAgentModelRequest,
)

router = APIRouter()


@router.get("/{agent_type}/model", response_model=AgentModelResponse)
async def get_model_for_agent(
    agent_type: str, llm_service: LLMService = Depends(get_llm_service)
) -> AgentModelResponse:
    """Get the preferred model for a specific agent type.

    Args:
        agent_type: The agent type to get the preferred model for

    Returns:
        The preferred model ID for the agent
    """
    # Validate agent type
    try:
        agent_enum = AgentType(agent_type)
    except ValueError:
        valid_types = [t.value for t in AgentType]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type: {agent_type}. Must be one of: {', '.join(valid_types)}",
        ) from None

    # Get the preferred model for this agent type
    model = llm_service.get_model_for_agent(agent_enum)

    return AgentModelResponse(model_id=model.id)


@router.get("/{agent_type}/available-models", response_model=AvailableModelsResponse)
async def get_available_models(
    agent_type: str,
    llm_service: LLMService = Depends(get_llm_service),
) -> AvailableModelsResponse:
    """Get available models for a specific agent type.

    Args:
        agent_type: Agent type to get available models for (project, task_specification, task_planning, task_implementation, investigation)
        llm_service: LLM service dependency

    Returns:
        Available models response for the specified agent type
    """
    # Validate agent type using AgentType enum directly
    try:
        agent_enum = AgentType(agent_type)
    except ValueError:
        valid_types = [t.value for t in AgentType]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type: {agent_type}. Must be one of: {', '.join(valid_types)}",
        ) from None

    # Get all available models and preferred model for this agent
    available_models = llm_service.get_available_models()
    selected_model = llm_service.get_model_for_agent(agent_enum)

    return AvailableModelsResponse(
        agent_type=agent_type,
        available_models=available_models,
        preferred_model=selected_model.id,
        total_available=len(available_models),
    )


@router.put("/{agent_type}/model", response_model=AgentModelResponse)
async def update_agent_model(
    agent_type: str,
    request: UpdateAgentModelRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> AgentModelResponse:
    """Update the preferred model for a specific agent type.

    Args:
        agent_type: Agent type to update model for (project, task_specification, task_planning, task_implementation, investigation)
        request: Model update request with selected model ID (or null to use default)
        llm_service: LLM service dependency

    Returns:
        The updated model information for the agent
    """
    # Validate agent type using AgentType enum directly
    try:
        agent_enum = AgentType(agent_type)
    except ValueError:
        valid_types = [t.value for t in AgentType]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent type: {agent_type}. Must be one of: {', '.join(valid_types)}",
        ) from None

    # Update the agent model using the service method
    llm_service.set_agent_model(agent_enum, request.model_id)
    agent_model = llm_service.get_model_for_agent(agent_enum)
    return AgentModelResponse(model_id=agent_model.id)
