"""Settings API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.services import get_integration_service
from devboard.api.schemas import IntegrationTestResponse
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

    return IntegrationTestResponse(
        integration_type=result.integration_type,
        success=result.success,
        error_message=result.error_message,
        error_type=result.error_type,
    )
