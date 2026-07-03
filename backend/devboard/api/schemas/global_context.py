"""Schemas for global context endpoints."""

from datetime import datetime

from pydantic import BaseModel


class GlobalContextResponse(BaseModel):
    content: str
    content_hash: str
    updated_at: datetime


class GlobalContextUpdate(BaseModel):
    content: str
