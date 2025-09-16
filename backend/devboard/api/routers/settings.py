"""Settings API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.llm_service import LLMService
from devboard.agents.types import AgentType
from devboard.api.dependencies.services import get_integration_service, get_llm_service
from devboard.api.schemas import AvailableModelsResponse, IntegrationTestResponse
from devboard.services.integration_service import IntegrationService

router = APIRouter()


@router.post("/integrations/{integration_type}/test", response_model=IntegrationTestResponse)
async def test_integration_connection(
    integration_type: str,
    integration_service: IntegrationService = Depends(get_integration_service),
) -> IntegrationTestResponse:
    """Test connection for a specific integration.

    Args:
        integration_type: One of 'github', 'jira', 'slack'

    Returns:
        Connection test results with status and details
    """
    result = await integration_service.test_integration_connection(integration_type)

    # Map to HTTP status codes for different error types
    if not result.success and result.error_type == "unsupported_integration":
        raise HTTPException(status_code=404, detail=result.error_message)

    return result


@router.get("/agents/available-models", response_model=AvailableModelsResponse)
async def get_available_models(
    agent_type: str | None = None,
    llm_service: LLMService = Depends(get_llm_service),
) -> AvailableModelsResponse:
    """Get available models for agents.

    Args:
        agent_type: Optional agent type to filter models for (project, task_specification, task_planning, task_implementation, investigation)
        llm_service: LLM service dependency

    Returns:
        Available models response for the specified agent type or all agents
    """
    # If agent_type is provided, validate it
    if agent_type:
        try:
            agent_enum = AgentType(agent_type)
        except ValueError:
            valid_types = [t.value for t in AgentType]
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent type: {agent_type}. Must be one of: {', '.join(valid_types)}",
            ) from None

        # Get models for specific agent type
        available_models = llm_service.get_available_models()
        preferred_model = llm_service.get_preferred_model_for_agent(agent_enum)

        # Import model hierarchies to include in response
        from devboard.config.llm_config import AGENT_MODEL_HIERARCHIES

        model_hierarchy = AGENT_MODEL_HIERARCHIES.get(agent_enum, [])

        return AvailableModelsResponse(
            agent_type=agent_type,
            available_models=available_models,
            preferred_model=preferred_model,
            total_available=len(available_models),
            model_hierarchy=model_hierarchy,
        )
    else:
        # Return models for all agent types (defaulting to first agent type for response format)
        available_models = llm_service.get_available_models()

        # Get model data for all agent types
        agent_models = {}
        from devboard.config.llm_config import AGENT_MODEL_HIERARCHIES

        for agent_enum in AgentType:
            preferred = llm_service.get_preferred_model_for_agent(agent_enum)
            hierarchy = AGENT_MODEL_HIERARCHIES.get(agent_enum, [])
            agent_models[agent_enum.value] = {
                "preferred_model": preferred,
                "model_hierarchy": hierarchy,
            }

        # Use a default agent type for the response structure
        default_agent = AgentType.PROJECT
        return AvailableModelsResponse(
            agent_type="all",  # Indicate this is for all agents
            available_models=available_models,
            preferred_model=llm_service.get_preferred_model_for_agent(default_agent),
            total_available=len(available_models),
            model_hierarchy=AGENT_MODEL_HIERARCHIES.get(default_agent, []),
        )
