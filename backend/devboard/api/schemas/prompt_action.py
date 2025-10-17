"""Schemas for prompt action API requests."""

from pydantic import BaseModel, Field


class PromptActionRequest(BaseModel):
    """Request to execute a prompt action.

    Attributes:
        action_key: The unique identifier for the action to execute
    """

    action_key: str = Field(..., description="Unique identifier for the prompt action to execute")
