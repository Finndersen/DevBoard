"""Dependency injection modules for FastAPI."""

from devboard.api.dependencies.resolver import DependencyResolver, resolve_dependency

__all__ = [
    "DependencyResolver",
    "resolve_dependency",
]
