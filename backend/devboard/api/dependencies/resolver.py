"""Dynamic dependency resolution for FastAPI.

This module provides utilities for resolving FastAPI dependencies outside of
normal request handling.

For conditional resolution within endpoints:
    workspace_service = await resolve_dependency(
        get_workspace_service, request=http_request
    )

For background jobs that need full lifecycle management:
    async with DependencyResolver() as resolver:
        await resolver.run(my_background_task, task_id=123)
"""

import inspect
from collections.abc import Callable
from contextlib import AsyncExitStack
from typing import Any

from fastapi import FastAPI
from fastapi.dependencies.utils import get_dependant, solve_dependencies
from starlette.requests import Request


class _OverridesProvider:
    """Minimal dependency overrides provider for use outside a FastAPI app context."""

    def __init__(self, overrides: dict[Callable, Callable]):
        self.dependency_overrides = overrides


async def resolve_dependency[T](
    func: Callable[..., T],
    *,
    request: Request,
    app: FastAPI | None = None,
) -> T:
    """
    Resolve a dependency function within a request context.

    Use this for conditional dependency resolution during request handling.

    WARNING — isolated DB session: FastAPI's dependency_cache is created as a local `{}` inside
    `solve_dependencies` and never stored in `request.scope`, so it is not accessible after the
    endpoint's Depends() chain has resolved. The cache used here only provides sharing between
    multiple `resolve_dependency` calls within the same request — it is isolated from the
    endpoint's own Depends() chain. As a result, shared dependencies like `get_db` are resolved
    fresh here, creating a new DB session separate from the one used by endpoint-resolved
    dependencies. For services that need to share the same DB session as the endpoint, declare
    them as standard Depends() parameters on the endpoint function instead.

    Args:
        func: Dependency function to resolve (e.g., get_workspace_service)
        request: The current HTTP request
        app: FastAPI app for dependency_overrides (optional)

    Returns:
        The resolved dependency value
    """
    exit_stack = request.scope.get("fastapi_inner_astack")
    if exit_stack is None:
        raise RuntimeError(
            "Request scope missing 'fastapi_inner_astack'. Ensure this is called within a FastAPI request context."
        )

    dependency_cache = request.scope.setdefault("dependency_cache", {})

    dependant = get_dependant(path="", call=func)

    solved = await solve_dependencies(
        request=request,
        dependant=dependant,
        dependency_cache=dependency_cache,
        async_exit_stack=exit_stack,
        embed_body_fields=False,
        dependency_overrides_provider=app,
    )

    if solved.errors:
        raise ValueError(f"Dependency resolution failed: {solved.errors}")

    # Call the function with resolved dependency values
    if inspect.iscoroutinefunction(func):
        return await func(**solved.values)
    else:
        return func(**solved.values)


class DependencyResolver:
    """
    Resolves FastAPI dependencies for background tasks outside request context.

    Use as async context manager to manage dependency lifecycle:

        async with DependencyResolver() as resolver:
            await resolver.run(my_background_task, task_id=123)
            # DB commits on successful exit, rolls back on exception
    """

    def __init__(
        self,
        *,
        app: FastAPI | None = None,
        dependency_overrides: dict[Callable, Callable] | None = None,
    ):
        """
        Initialize resolver.

        Args:
            app: FastAPI app for dependency_overrides support (optional)
            dependency_overrides: Additional dependency overrides to apply, merged with any
                app-level overrides. Useful for injecting pre-constructed values (e.g. a
                manually-managed DB session) while still auto-resolving everything else.
        """
        base = dict(app.dependency_overrides) if app else {}
        merged = {**base, **(dependency_overrides or {})}
        self._overrides_provider: FastAPI | _OverridesProvider | None = _OverridesProvider(merged) if merged else app
        self._exit_stack: AsyncExitStack | None = None
        self._dependency_cache: dict[Any, Any] = {}

    async def __aenter__(self) -> "DependencyResolver":
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    def _create_mock_request(self) -> Request:
        """Create minimal mock request for dependency resolution."""
        scope: dict[str, Any] = {
            "type": "http",
            "method": "POST",
            "path": "/background",
            "query_string": b"",
            "headers": [],
            "fastapi_inner_astack": self._exit_stack,
            "fastapi_function_astack": self._exit_stack,
            "dependency_cache": self._dependency_cache,
        }
        return Request(scope)

    async def run[T](
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Resolve dependencies for a function and execute it.

        Dependencies are resolved from the function's signature (parameters
        with Depends() defaults). Resolved values are cached within the
        resolver's scope.

        Args:
            func: Function with Depends() parameters in signature
            *args: Positional arguments to pass through
            **kwargs: Keyword arguments (can override resolved dependencies)

        Returns:
            The function's return value
        """
        if self._exit_stack is None:
            raise RuntimeError("DependencyResolver must be used as async context manager")

        dependant = get_dependant(path="", call=func)

        # Clear non-dependency parameters (query, header, cookie, body params)
        # These would fail resolution since we're not in a real HTTP request context.
        dependant.query_params = []
        dependant.header_params = []
        dependant.cookie_params = []
        dependant.body_params = []

        request = self._create_mock_request()
        solved = await solve_dependencies(
            request=request,
            dependant=dependant,
            dependency_cache=self._dependency_cache,
            async_exit_stack=self._exit_stack,
            embed_body_fields=False,
            dependency_overrides_provider=self._overrides_provider,
        )

        if solved.errors:
            raise ValueError(f"Dependency resolution failed: {solved.errors}")

        all_kwargs = {**solved.values, **kwargs}

        if inspect.iscoroutinefunction(func):
            return await func(*args, **all_kwargs)
        else:
            return func(*args, **all_kwargs)
