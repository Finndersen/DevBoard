"""Tool for rendering HTML content in the frontend."""

import json

from pydantic_ai import Tool


def create_render_html_tool() -> Tool:
    """Create a tool that allows the agent to render HTML content in a sandboxed iframe.

    This tool enables agents to generate rich visualizations, dashboards, charts, styled
    tables, or other interactive read-only content. The HTML is rendered in a sandboxed
    iframe that can execute JavaScript and load external CDN resources (e.g., Chart.js,
    D3.js) but cannot access the parent page.

    Returns:
        Tool: A PydanticAI tool for rendering HTML content.
    """

    async def render_html(title: str, html: str) -> str:
        """Render HTML content in a sandboxed iframe in the frontend.

        The HTML will be displayed in a modal dialog with the provided title. The content
        is rendered in a sandboxed iframe that:
        - Can execute JavaScript (allow-scripts)
        - Can load external resources from CDNs
        - Cannot access the parent page (no allow-same-origin)

        The HTML should be a complete, self-contained HTML document including <html>,
        <head>, <style>, and <script> tags as needed. You can use external libraries
        from CDNs like Chart.js, D3.js, etc.

        Use this tool when the user requests something visual or when the content would
        benefit significantly from rich formatting beyond Markdown (e.g., charts,
        dashboards, interactive tables, diagrams).

        Args:
            title: A short descriptive title for the content (shown in modal header).
            html: Complete self-contained HTML document to render.
        """
        return json.dumps({"title": title, "html": html})

    return Tool(function=render_html, name="render_html")
