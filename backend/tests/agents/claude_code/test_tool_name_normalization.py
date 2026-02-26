"""Tests for tool name normalization logic."""

from devboard.agents.engines.claude_code.utils import normalize_tool_name


class TestNormalizeToolName:
    """Test the normalize_tool_name() function."""

    def test_normalize_builtin_tools(self):
        """Should strip mcp__builtin_tools__ prefix."""
        assert normalize_tool_name("mcp__builtin_tools__render_html") == "render_html"
        assert normalize_tool_name("mcp__builtin_tools__create_task") == "create_task"
        assert normalize_tool_name("mcp__builtin_tools__Read") == "Read"

    def test_preserve_external_mcp_tools(self):
        """Should NOT strip external MCP server prefixes - only builtin_tools."""
        assert normalize_tool_name("mcp__github__create_issue") == "mcp__github__create_issue"
        assert normalize_tool_name("mcp__jira__update_ticket") == "mcp__jira__update_ticket"
        assert normalize_tool_name("mcp__filesystem__read_file") == "mcp__filesystem__read_file"

    def test_preserve_non_mcp_names(self):
        """Should not modify non-MCP tool names."""
        assert normalize_tool_name("render_html") == "render_html"
        assert normalize_tool_name("create_task") == "create_task"
        assert normalize_tool_name("Read") == "Read"
        assert normalize_tool_name("simple_tool") == "simple_tool"

    def test_preserve_underscores_in_tool_names(self):
        """Should preserve double underscores in actual tool names."""
        # Tool name itself contains underscores (not an MCP prefix)
        assert normalize_tool_name("my__custom__tool") == "my__custom__tool"
        assert normalize_tool_name("get__user__data") == "get__user__data"

        # Builtin tool with underscores in the name
        assert normalize_tool_name("mcp__builtin_tools__my__custom__tool") == "my__custom__tool"

        # External MCP tool with underscores keeps full prefix
        assert normalize_tool_name("mcp__github__get__repo__info") == "mcp__github__get__repo__info"

    def test_edge_cases(self):
        """Should handle edge cases gracefully."""
        # Empty string
        assert normalize_tool_name("") == ""

        # Simple names
        assert normalize_tool_name("tool") == "tool"

        # Just "mcp" (not a valid pattern)
        assert normalize_tool_name("mcp") == "mcp"

        # "mcp__" without enough parts (invalid pattern)
        assert normalize_tool_name("mcp__") == "mcp__"
        assert normalize_tool_name("mcp__tool") == "mcp__tool"

        # Single underscore (not double)
        assert normalize_tool_name("mcp_tool") == "mcp_tool"

    def test_pattern_validation(self):
        """Should only strip mcp__builtin_tools__ prefix."""
        # Must start with exact prefix "mcp__builtin_tools__"
        assert normalize_tool_name("not_mcp__builtin_tools__tool") == "not_mcp__builtin_tools__tool"

        # Other MCP servers are not stripped
        assert normalize_tool_name("mcp__other_server__tool") == "mcp__other_server__tool"
        assert normalize_tool_name("mcp__github__tool") == "mcp__github__tool"

        # Valid builtin_tools pattern
        assert normalize_tool_name("mcp__builtin_tools__tool") == "tool"
        assert normalize_tool_name("mcp__builtin_tools__t") == "t"
