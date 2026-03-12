"""Dependency injection modules for FastAPI."""

from devboard.api.dependencies.resolver import DependencyResolver, call_with_dependencies

__all__ = [
    "DependencyResolver",
    "call_with_dependencies",
]
