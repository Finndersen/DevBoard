"""Common Pydantic schemas used across multiple endpoints."""

from pydantic import BaseModel


class DeleteResponse(BaseModel):
    """Standard response schema for DELETE endpoints."""

    message: str
    success: bool = True


class ResetConversationResponse(BaseModel):
    """Response schema for conversation reset endpoint."""

    new_conversation_id: int
    message: str
