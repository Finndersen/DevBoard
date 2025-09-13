"""Settings API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.agents.llm_service import LLMService
from devboard.agents.types import AgentType
from devboard.api.dependencies.services import get_integration_service, get_llm_service
from devboard.api.schemas import AgentModelResponse, IntegrationTestResponse
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


@router.get("/agents/{agent_type}/model", response_model=AgentModelResponse)
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
    model_id = llm_service.get_preferred_model_for_agent(agent_enum)

    return AgentModelResponse(model_id=model_id)
