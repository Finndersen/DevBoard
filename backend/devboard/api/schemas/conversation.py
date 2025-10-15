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
    model_id: str
    is_active: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
