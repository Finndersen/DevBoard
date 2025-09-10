"""Settings API endpoints."""

from fastapi import APIRouter, HTTPException

from devboard.agents.llm_service import llm_service
from devboard.agents.types import AgentType
from devboard.api.schemas import AvailableModelsResponse, IntegrationTestResponse
from devboard.services.integration_service import IntegrationService

router = APIRouter()


@router.post("/integrations/{integration_type}/test", response_model=IntegrationTestResponse)
async def test_integration_connection(integration_type: str) -> IntegrationTestResponse:
    """Test connection for a specific integration.

    Args:
        integration_type: One of 'github', 'jira', 'slack'

    Returns:
        Connection test results with status and details
    """
    integration_service = IntegrationService()
    result = await integration_service.test_integration_connection(integration_type)

    # Map to HTTP status codes for different error types
    if not result.success and result.error_type == "unsupported_integration":
        raise HTTPException(status_code=404, detail=result.error_message)

    return result


@router.get("/agents/available-models", response_model=AvailableModelsResponse)
async def get_available_models(agent_type: str = None) -> AvailableModelsResponse:
    """Get available models for agents.

    Args:
        agent_type: Optional specific agent type to get models for

    Returns:
        Available models and recommendations
    """
    # Get all available models once
    all_models = llm_service.get_available_models()
    # Convert to list of ModelInfo for schema compatibility
    models_list = [
        {"id": model.id, "provider": model.provider, "name": model.name} for model in all_models
    ]

    if agent_type:
        # Validate agent type
        try:
            agent_enum = AgentType(agent_type)
        except ValueError:
            valid_types = [t.value for t in AgentType]
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent type: {agent_type}. Must be one of: {', '.join(valid_types)}",
            ) from None

        preferred_model = llm_service.get_preferred_model_for_agent(agent_enum)

        return AvailableModelsResponse(
            agent_type=agent_type,
            available_models=models_list,
            preferred_model=preferred_model,
            total_available=len(models_list),
        )

    else:
        # Return models for all agent types
        result_data = {}
        for agent_enum in AgentType:
            preferred_model = llm_service.get_preferred_model_for_agent(agent_enum)
            result_data[agent_enum.value] = {
                "available_models": models_list,
                "preferred_model": preferred_model,
                "total_available": len(models_list),
            }

        return AvailableModelsResponse(
            qa=result_data.get("qa"),
            planning=result_data.get("planning"),
            implementation=result_data.get("implementation"),
        )
