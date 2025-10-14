"""Web page context provider for generic web page content."""

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from .base import (
    BaseContextProvider,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)


class WebPageContextProvider(BaseContextProvider):
    """Context provider for generic web pages."""

    provider_type = "webpage"

    @classmethod
    def create_instance(cls) -> "WebPageContextProvider":
        """Create an instance of the web page context provider.

        Web pages require no external configuration, so this always succeeds.

        Returns:
            Configured WebPageContextProvider instance
        """
        return cls()

    def __init__(self, max_content_length: int = 10000):
        """Initialize web page provider.

        Args:
            max_content_length: Maximum length of extracted text content
        """
        self.max_content_length = max_content_length

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        """Check if URI is a web page (http/https)."""
        parsed = urlparse(resource_uri)
        return parsed.scheme in ["http", "https"]

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        """Web pages are small-scope resources loaded eagerly."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        return ContextStrategy.EAGER

    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Fetch and process web page content."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "DevBoard/1.0 (Context Provider)"},
            ) as client:
                response = await client.get(resource_uri)
                response.raise_for_status()

                # Process HTML content
                processed_content = self._process_html_content(response.text)

                return {
                    "type": "webpage",
                    "uri": resource_uri,
                    "title": processed_content["title"],
                    "content": processed_content["text"],
                    "url": resource_uri,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "word_count": len(processed_content["text"].split()),
                }

        except httpx.HTTPError as e:
            raise ContextRetrievalError(f"Failed to fetch web page {resource_uri}: {e}") from e
        except Exception as e:
            raise ContextRetrievalError(f"Error processing web page {resource_uri}: {e}") from e

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        """For web pages, return the full processed content since they're EAGER."""
        resource_data = await self.get_resource(resource_uri)

        title = resource_data.get("title", "")
        content = resource_data.get("content", "")

        return f"**{title}**\n\n{content}"

    async def generate_resource_description(self, resource_uri: str) -> str:
        """Generate a description of the web page content."""
        try:
            resource_data = await self.get_resource(resource_uri)

            title = resource_data.get("title", "")
            content = resource_data.get("content", "")
            word_count = resource_data.get("word_count", 0)

            # Create a summary based on title and first part of content
            description_parts = []

            if title:
                description_parts.append(f"Web page: {title}")
            else:
                parsed = urlparse(resource_uri)
                description_parts.append(f"Web page from {parsed.netloc}")

            if content:
                # Get first sentence or first 100 characters
                first_sentence = content.split(".")[0]
                if len(first_sentence) > 100:
                    summary = content[:100] + "..."
                else:
                    summary = first_sentence + "."

                description_parts.append(f"Content: {summary}")

            description_parts.append(f"({word_count} words)")

            return " ".join(description_parts)

        except Exception as e:
            raise DescriptionGenerationError(f"Failed to generate description for {resource_uri}: {e}") from e

    def _process_html_content(self, html_content: str) -> dict[str, str]:
        """Process HTML content to extract clean text and metadata.

        Args:
            html_content: Raw HTML content

        Returns:
            Dictionary with processed title and text content
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else ""

        # Remove unwanted elements
        for element in soup(
            [
                "script",
                "style",
                "nav",
                "header",
                "footer",
                "aside",
                "noscript",
                "iframe",
                "object",
                "embed",
                "form",
            ]
        ):
            element.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, type(soup.new_string("")))):
            if str(comment).strip().startswith("<!--"):
                comment.extract()

        # Extract main content areas (prioritize main content)
        content_element: Tag | BeautifulSoup | None = None
        for selector in ["main", "article", '[role="main"]', ".content", "#content", ".post"]:
            content_element = soup.select_one(selector)
            if content_element:
                break

        # If no main content area found, use body
        if not content_element:
            body_element = soup.find("body")
            content_element = body_element if body_element is not None else soup

        # Extract text and clean it up
        if content_element is not None:
            extracted_text = content_element.get_text()
        else:
            extracted_text = ""

        # Clean up whitespace
        extracted_text = re.sub(r"\s+", " ", extracted_text)
        extracted_text = extracted_text.strip()

        # Truncate if too long
        if len(extracted_text) > self.max_content_length:
            extracted_text = extracted_text[: self.max_content_length] + "..."

        return {"title": title, "text": extracted_text}
