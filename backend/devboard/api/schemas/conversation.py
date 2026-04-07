"""Conversation schemas."""

import datetime

from pydantic import BaseModel

from devboard.agents.events import ContextUsage, ConversationEvent


class ConversationMessagesResponse(BaseModel):
    """Response schema for conversation messages endpoint."""

    messages: list[ConversationEvent]
    context_usage: ContextUsage | None = None


class ConversationResponse(BaseModel):
    """Unified response schema for conversation details and list items."""

    id: int
    parent_entity_type: str
    parent_entity_id: int
    agent_role: str
    engine: str
    model_id: str | None
    is_active: bool
    external_session_id: str | None
    title: str | None = None
    last_activity_at: datetime.datetime | None = None
    created_at: datetime.datetime
    parent_entity_name: str | None = None
    project_name: str | None = None

    model_config = {"from_attributes": True}


class ConversationUpdate(BaseModel):
    """Request schema for updating a conversation."""

    title: str


class CreateConversationResponse(ConversationResponse):
    """Response schema for creating a project conversation."""

    at_cap: bool
