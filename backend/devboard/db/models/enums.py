"""Shared enums for database models."""

from enum import StrEnum


class EntityType(StrEnum):
    """Type of domain entity (project, task, codebase, background_agent)."""

    PROJECT = "project"
    TASK = "task"
    CODEBASE = "codebase"
    BACKGROUND_AGENT = "background_agent"


# Alias for backwards compatibility with existing conversation model usage
ParentEntityType = EntityType
