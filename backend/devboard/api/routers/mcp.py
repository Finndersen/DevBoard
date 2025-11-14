"""MCP (Model Context Protocol) endpoints.

This module provides HTTP endpoints for the MCP server,
allowing AI clients to connect and interact with DevBoard.

The MCP server is mounted as an ASGI application and handles:
- /mcp - HTTP transport (MCP protocol over HTTP)
"""

from devboard.mcp import mcp

# Export the MCP server as an ASGI application
# Uses http_app() from jlowin/fastmcp to provide HTTP transport
mcp_app = mcp.http_app(path="/mcp")
