"""MCP (Model Context Protocol) endpoints.

This module provides Streamable HTTP endpoints for the MCP server,
allowing AI clients to connect and interact with DevBoard.

The MCP server is mounted as an ASGI application and handles:
- /mcp - Streamable HTTP transport (current standard)
"""

from devboard.mcp import mcp

# Export the MCP server as an ASGI application
# The official SDK's FastMCP.streamable_http_app() provides the Streamable HTTP transport
mcp_app = mcp.streamable_http_app()
