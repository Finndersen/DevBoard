"""OAuth API endpoints."""

import logfire
from fastapi import APIRouter, Depends, HTTPException

from devboard.api.dependencies.services import get_oauth_service
from devboard.api.schemas.oauth import OAuthCallbackError, OAuthCallbackQueryParams, OAuthCallbackResponse
from devboard.services.oauth_service import OAuthService, OAuthStateMismatchError

router = APIRouter()


@router.get(
    "/callback/{provider_key}",
    response_model=OAuthCallbackResponse,
    responses={
        200: {"model": OAuthCallbackResponse, "description": "Authorization code received successfully"},
        400: {"model": OAuthCallbackError, "description": "Missing authorization code or invalid request"},
        404: {"model": OAuthCallbackError, "description": "No pending authorization found"},
    },
)
async def oauth_callback(
    provider_key: str,
    params: OAuthCallbackQueryParams = Depends(),
    oauth_service: OAuthService = Depends(get_oauth_service),
) -> OAuthCallbackResponse:
    """Handle OAuth callback from authorization server.

    This endpoint receives the authorization code from the OAuth provider's redirect
    and stores it in the pending authorization record. The consumer (MCP SDK or
    traditional OAuth flow) is responsible for polling and exchanging the code.

    Args:
        provider_key: Unique identifier for the OAuth context (e.g., "oauth-1" or "mcp-1")
        params: OAuth callback query parameters (code, state, error, error_description)

    Returns:
        Success response with provider_key

    Raises:
        HTTPException: If authorization failed or code is missing
    """
    logfire.info(f"OAuth callback received for provider_key:{provider_key}")

    # Handle error responses from OAuth provider
    if params.error:
        logfire.warn(f"OAuth error for provider_key:{provider_key}: {params.error} - {params.error_description}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": f"{params.error}: {params.error_description or 'Authorization denied'}",
                "provider_key": provider_key,
            },
        )

    # Validate authorization code is present
    if not params.code:
        logfire.warn(f"No authorization code for provider_key:{provider_key}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "Missing authorization code",
                "provider_key": provider_key,
            },
        )

    # Store the authorization code
    try:
        result = oauth_service.store_authorization_code(
            provider_key=provider_key,
            authorization_code=params.code,
            state=params.state,
        )
    except OAuthStateMismatchError:
        logfire.warn(f"State mismatch for provider_key:{provider_key}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": "State parameter mismatch",
                "provider_key": provider_key,
            },
        ) from None

    if not result:
        logfire.warn(f"No pending authorization found for provider_key:{provider_key}")
        raise HTTPException(
            status_code=404,
            detail={
                "success": False,
                "error": "No pending authorization found",
                "provider_key": provider_key,
            },
        )

    logfire.info(f"Authorization code stored for provider_key:{provider_key}")

    return OAuthCallbackResponse(
        success=True,
        message="Authorization code received successfully",
        provider_key=provider_key,
    )
