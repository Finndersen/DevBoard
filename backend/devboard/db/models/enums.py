"""Shared enums for database models."""

from enum import StrEnum


class EntityType(StrEnum):
    """Type of domain entity (project, task, codebase)."""

    PROJECT = "project"
    TASK = "task"
    CODEBASE = "codebase"


# Alias for backwards compatibility with existing conversation model usage
ParentEntityType = EntityType
