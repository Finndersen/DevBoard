"""Tests for render_html tool."""

import json

import pytest
from pydantic_ai import Tool

from devboard.agents.tools.render_html import create_render_html_tool


class TestCreateRenderHtmlTool:
    """Tests for create_render_html_tool factory function."""

    def test_creates_tool_with_correct_name(self):
        """Tool is created with name 'render_html'."""
        tool = create_render_html_tool()

        assert isinstance(tool, Tool)
        assert tool.name == "render_html"

    @pytest.mark.asyncio
    async def test_render_html_returns_json_with_title_and_html(self):
        """Tool function returns JSON string with title and html fields."""
        tool = create_render_html_tool()

        title = "Test Visualization"
        html = "<html><body><h1>Hello World</h1></body></html>"

        result = await tool.function(title=title, html=html)

        # Parse the JSON result
        parsed = json.loads(result)
        assert parsed["title"] == title
        assert parsed["html"] == html

    @pytest.mark.asyncio
    async def test_render_html_handles_complex_html(self):
        """Tool function handles complex HTML with scripts and styles."""
        tool = create_render_html_tool()

        title = "Chart Dashboard"
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .chart { width: 100%; height: 400px; }
            </style>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        </head>
        <body>
            <div class="chart" id="myChart"></div>
            <script>
                const ctx = document.getElementById('myChart').getContext('2d');
                new Chart(ctx, { type: 'bar', data: {} });
            </script>
        </body>
        </html>
        """

        result = await tool.function(title=title, html=html)

        parsed = json.loads(result)
        assert parsed["title"] == title
        assert parsed["html"] == html
        assert "chart.js" in parsed["html"]
        assert "<script>" in parsed["html"]

    @pytest.mark.asyncio
    async def test_render_html_preserves_special_characters(self):
        """Tool function preserves special characters in HTML."""
        tool = create_render_html_tool()

        title = "Special Characters & Entities"
        html = '<html><body><p>Test &amp; "quotes" &lt;tags&gt;</p></body></html>'

        result = await tool.function(title=title, html=html)

        parsed = json.loads(result)
        assert parsed["title"] == title
        assert parsed["html"] == html
        assert "&amp;" in parsed["html"]
        assert "&lt;" in parsed["html"]
