"""Unit tests for dependency resolution utilities."""

from contextlib import AsyncExitStack
from unittest.mock import Mock

import pytest
from fastapi import Depends

from devboard.api.dependencies.resolver import DependencyResolver, call_with_dependencies


# Test dependencies
def get_simple_dep() -> str:
    return "resolved_value"


async def get_async_dep() -> int:
    return 42


def get_chained_dep(simple: str = Depends(get_simple_dep)) -> dict:
    return {"simple": simple}


class TestResolveDependency:
    """Tests for resolve_dependency function (within request context)."""

    @pytest.mark.asyncio
    async def test_resolves_simple_dependency(self):
        """Test resolving a dependency with no sub-dependencies."""
        exit_stack = AsyncExitStack()
        await exit_stack.__aenter__()

        mock_request = Mock()
        mock_request.scope = {
            "fastapi_inner_astack": exit_stack,
            "dependency_cache": {},
        }

        result = await call_with_dependencies(get_simple_dep, request=mock_request)

        assert result == "resolved_value"
        await exit_stack.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_resolves_chained_dependency(self):
        """Test resolving a dependency with sub-dependencies."""
        exit_stack = AsyncExitStack()
        await exit_stack.__aenter__()

        mock_request = Mock()
        mock_request.scope = {
            "fastapi_inner_astack": exit_stack,
            "dependency_cache": {},
        }

        result = await call_with_dependencies(get_chained_dep, request=mock_request)

        assert result == {"simple": "resolved_value"}
        await exit_stack.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_caches_sub_dependencies_in_request_scope(self):
        """Test that sub-dependencies are cached in request's cache."""
        exit_stack = AsyncExitStack()
        await exit_stack.__aenter__()

        mock_request = Mock()
        mock_request.scope = {
            "fastapi_inner_astack": exit_stack,
            "dependency_cache": {},
        }

        call_count = 0

        def counting_dep() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        def uses_counting(val: int = Depends(counting_dep)) -> int:
            return val

        result1 = await call_with_dependencies(uses_counting, request=mock_request)
        result2 = await call_with_dependencies(uses_counting, request=mock_request)

        # The sub-dependency (counting_dep) should be cached across calls
        assert result1 == result2 == 1
        assert call_count == 1

        await exit_stack.__aexit__(None, None, None)

    @pytest.mark.asyncio
    async def test_error_when_missing_exit_stack(self):
        """Test that clear error is raised when request scope is missing exit stack."""
        mock_request = Mock()
        mock_request.scope = {}

        with pytest.raises(RuntimeError, match="missing 'fastapi_inner_astack'"):
            await call_with_dependencies(get_simple_dep, request=mock_request)


class TestDependencyResolver:
    """Tests for DependencyResolver (background task usage)."""

    @pytest.mark.asyncio
    async def test_run_resolves_sync_dependency(self):
        """Test that run() resolves sync dependencies."""

        async def my_func(dep: str = Depends(get_simple_dep)) -> str:
            return f"got: {dep}"

        async with DependencyResolver() as resolver:
            result = await resolver.run(my_func)

        assert result == "got: resolved_value"

    @pytest.mark.asyncio
    async def test_run_resolves_async_dependency(self):
        """Test that run() resolves async dependencies."""

        async def my_func(dep: int = Depends(get_async_dep)) -> int:
            return dep * 2

        async with DependencyResolver() as resolver:
            result = await resolver.run(my_func)

        assert result == 84

    @pytest.mark.asyncio
    async def test_run_resolves_chained_dependencies(self):
        """Test that run() resolves nested/chained dependencies."""

        async def my_func(dep: dict = Depends(get_chained_dep)) -> dict:
            return dep

        async with DependencyResolver() as resolver:
            result = await resolver.run(my_func)

        assert result == {"simple": "resolved_value"}

    @pytest.mark.asyncio
    async def test_run_passes_explicit_kwargs(self):
        """Test that explicit keyword args are passed through."""

        async def my_func(
            task_id: int,
            message: str,
            dep: str = Depends(get_simple_dep),
        ) -> str:
            return f"task {task_id} ({message}): {dep}"

        async with DependencyResolver() as resolver:
            result = await resolver.run(my_func, task_id=123, message="hello")

        assert result == "task 123 (hello): resolved_value"

    @pytest.mark.asyncio
    async def test_run_allows_dependency_override(self):
        """Test that explicit kwargs override resolved dependencies."""

        async def my_func(dep: str = Depends(get_simple_dep)) -> str:
            return dep

        async with DependencyResolver() as resolver:
            result = await resolver.run(my_func, dep="overridden")

        assert result == "overridden"

    @pytest.mark.asyncio
    async def test_dependency_caching_within_scope(self):
        """Test that same dependency returns cached value within resolver scope."""
        call_count = 0

        def counting_dep() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        async def func1(dep: int = Depends(counting_dep)) -> int:
            return dep

        async def func2(dep: int = Depends(counting_dep)) -> int:
            return dep

        async with DependencyResolver() as resolver:
            result1 = await resolver.run(func1)
            result2 = await resolver.run(func2)

        assert result1 == result2 == 1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_generator_dependency_cleanup_on_success(self):
        """Test that generator dependencies are cleaned up on successful exit."""
        cleanup_called = False

        def tracked_generator():
            nonlocal cleanup_called
            try:
                yield "value"
            finally:
                cleanup_called = True

        async def my_func(dep: str = Depends(tracked_generator)) -> str:
            return dep

        async with DependencyResolver() as resolver:
            result = await resolver.run(my_func)
            assert result == "value"
            assert not cleanup_called

        assert cleanup_called

    @pytest.mark.asyncio
    async def test_generator_dependency_cleanup_on_error(self):
        """Test that generator cleanup runs even when error is raised."""
        cleanup_called = False

        def tracked_generator():
            nonlocal cleanup_called
            try:
                yield "value"
            finally:
                cleanup_called = True

        async def failing_func(_dep: str = Depends(tracked_generator)) -> str:
            raise ValueError("intentional error")

        with pytest.raises(ValueError, match="intentional error"):
            async with DependencyResolver() as resolver:
                await resolver.run(failing_func)

        assert cleanup_called

    @pytest.mark.asyncio
    async def test_error_when_used_outside_context_manager(self):
        """Test that run() raises error if used outside async with."""
        resolver = DependencyResolver()

        async def my_func(dep: str = Depends(get_simple_dep)) -> str:
            return dep

        with pytest.raises(RuntimeError, match="must be used as async context manager"):
            await resolver.run(my_func)

    @pytest.mark.asyncio
    async def test_run_sync_function(self):
        """Test that run() works with sync target functions."""

        def sync_func(dep: str = Depends(get_simple_dep)) -> str:
            return f"sync: {dep}"

        async with DependencyResolver() as resolver:
            result = await resolver.run(sync_func)

        assert result == "sync: resolved_value"
