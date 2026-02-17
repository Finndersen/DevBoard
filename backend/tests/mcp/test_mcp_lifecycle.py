from devboard.mcp.mcp_lifecycle import _unwrap_exception_group


class TestUnwrapExceptionGroup:
    def test_unwraps_single_exception_group(self) -> None:
        original = ValueError("bad command args")
        group = ExceptionGroup("task group error", [original])
        result = _unwrap_exception_group(group)
        assert result is original

    def test_unwraps_nested_single_exception_groups(self) -> None:
        original = RuntimeError("connection refused")
        inner = ExceptionGroup("inner", [original])
        outer = ExceptionGroup("outer", [inner])
        result = _unwrap_exception_group(outer)
        assert result is original

    def test_returns_plain_exception_unchanged(self) -> None:
        original = ValueError("simple error")
        result = _unwrap_exception_group(original)
        assert result is original

    def test_multi_exception_group_returned_as_is(self) -> None:
        group = ExceptionGroup("multiple", [ValueError("a"), TypeError("b")])
        result = _unwrap_exception_group(group)
        assert result is group
