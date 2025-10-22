"""Conversation schemas."""

import datetime

from pydantic import BaseModel


class ConversationResponse(BaseModel):
    """Response schema for conversation details."""

    id: int
    parent_entity_type: str
    parent_entity_id: int
    agent_role: str
    engine: str
    model_id: str | None
    is_active: bool
    external_session_id: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
