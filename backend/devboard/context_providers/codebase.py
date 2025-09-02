"""Codebase context provider for file and repository context using AI analysis."""

import logging
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from devboard.integrations.filesystem import FilesystemIntegration

from .base import (
    BaseContextProvider,
    ContextProviderUnavailable,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)

logger = logging.getLogger(__name__)


class CodebaseContextProvider(BaseContextProvider):
    """Context provider for codebase resources using AI-powered code analysis."""

    provider_type = "codebase"

    @classmethod
    def create_instance(cls) -> "CodebaseContextProvider":
        """Create an instance of the codebase context provider.

        Uses the current working directory as the base path and creates
        a filesystem integration. No external configuration required.

        Returns:
            Configured CodebaseContextProvider instance
        """
        import os

        try:
            integration = FilesystemIntegration()
            current_dir = os.getcwd()
            return cls(integration, current_dir)
        except Exception as e:
            raise ContextProviderUnavailable(
                f"Failed to initialize Codebase integration: {e}"
            ) from e

    def __init__(self, integration: FilesystemIntegration, base_path: str | None = None):
        """Initialize with Filesystem integration and optional base path."""
        self.integration = integration
        self.base_path = Path(base_path or Path.cwd()).resolve()

    @classmethod
    def can_handle_uri(cls, resource_uri: str) -> bool:
        """Check if URI is a codebase resource (file path or file:// URL)."""
        # Handle file:// URLs, absolute paths, or relative paths
        if resource_uri.startswith("file://"):
            return True
        elif resource_uri.startswith("/"):
            return True
        elif not urlparse(resource_uri).scheme:
            # Relative path or filename
            return True
        return False

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        """Determine strategy based on resource type.

        Single files are EAGER (small-scope), directories are ON_DEMAND (large-scope).
        """
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        normalized_path = self._normalize_file_path(resource_uri)
        full_path = self.base_path / normalized_path

        # Single files are EAGER, directories are ON_DEMAND
        if full_path.is_file():
            return ContextStrategy.EAGER
        else:
            return ContextStrategy.ON_DEMAND

    def _normalize_file_path(self, resource_uri: str) -> str:
        """Normalize resource URI to a relative file path."""
        if resource_uri.startswith("file://"):
            # Remove file:// prefix and convert to relative path
            file_path = resource_uri[7:]
            return self.integration.parse_file_url(file_path, str(self.base_path)) or file_path
        elif resource_uri.startswith("/"):
            # Absolute path - convert to relative
            return (
                self.integration.parse_file_url(resource_uri, str(self.base_path)) or resource_uri
            )
        else:
            # Assume relative path
            return resource_uri

    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Get full resource data for EAGER strategy (not typically used for codebase)."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            file_path = self._normalize_file_path(resource_uri)

            # Get file content and metadata
            content = await self.integration.read_file(file_path, str(self.base_path))
            file_info = await self.integration.get_file_info(file_path, str(self.base_path))

            return {"content": content, "file_info": file_info, "uri": resource_uri}

        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting codebase resource for {resource_uri}: {e}")
            raise ContextRetrievalError(f"Failed to get codebase resource: {e}") from e

    async def get_relevant_context(self, resource_uri: str, query: str) -> str:
        """Get query-relevant context from codebase using AI analysis."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            file_path = self._normalize_file_path(resource_uri)

            # Check if it's a specific file or directory-level query
            full_path = self.base_path / file_path
            if full_path.is_file():
                # Specific file - use AI to analyze file content with query context
                analysis_context = f"""
File: {file_path}
Query: {query}

Please analyze this specific file and provide insights relevant to the query.
Focus on the implementation details, patterns, and relationships within this file.
"""
                return await self._investigate_codebase(query, analysis_context)

            elif full_path.is_dir():
                # Directory - use AI to analyze directory structure and contents
                analysis_context = f"""
Directory: {file_path}
Query: {query}

Please analyze this directory structure and its contents.
Focus on the overall organization, key files, and architectural patterns.
"""
                return await self._investigate_codebase(query, analysis_context)

            else:
                # Pattern or general codebase query
                analysis_context = f"""
Codebase Pattern/Query: {file_path}
Query: {query}

Please search and analyze the codebase for patterns, implementations, or concepts related to this query.
"""
                return await self._investigate_codebase(query, analysis_context)
        except Exception as e:
            if isinstance(e, ResourceHandlingError | ContextRetrievalError):
                raise
            logger.error(f"Error getting codebase context for {resource_uri}: {e}")
            raise ContextRetrievalError(f"Failed to get codebase context: {e}") from e

    async def generate_resource_description(self, resource_uri: str) -> str:
        """Generate description for codebase resource."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            file_path = self._normalize_file_path(resource_uri)

            full_path = self.integration.base_path / file_path
            if full_path.is_file():
                # Get file info and generate description
                file_info = await self.integration.get_file_info(file_path, str(self.base_path))
                file_size = file_info.get("size", 0)

                # Try to determine file type from extension
                suffix = full_path.suffix
                if suffix in [".py", ".js", ".ts", ".java", ".cpp", ".c"]:
                    return f"Code file: {file_path} ({suffix[1:].upper()}, {file_size} bytes)"
                elif suffix in [".md", ".txt", ".rst"]:
                    return f"Documentation: {file_path} ({suffix[1:].upper()}, {file_size} bytes)"
                elif suffix in [".json", ".yaml", ".yml", ".toml"]:
                    return f"Configuration: {file_path} ({suffix[1:].upper()}, {file_size} bytes)"
                else:
                    return f"File: {file_path} ({file_size} bytes)"

            elif full_path.is_dir():
                # Count files in directory
                files = await self.integration.list_files(file_path, base_path=str(self.base_path))
                return f"Directory: {file_path} ({len(files)} files)"
            else:
                return f"Codebase pattern: {file_path}"
        except Exception as e:
            if isinstance(e, ResourceHandlingError | DescriptionGenerationError):
                raise
            logger.error(f"Error generating codebase description for {resource_uri}: {e}")
            raise DescriptionGenerationError(f"Failed to generate codebase description: {e}") from e

    async def _investigate_codebase(self, query: str, context: str = "") -> str:
        """High-level codebase investigation using Gemini CLI agent.

        Args:
            query: The investigation question or task
            context: Additional context about what to focus on

        Returns:
            AI-generated analysis and findings
        """
        try:
            full_prompt = f"""
You are analyzing a codebase located at: {self.base_path}

Investigation Query: {query}

Additional Context: {context}

Please analyze the codebase structure, patterns, and implementation to answer the query.
Focus on providing specific, actionable insights about the code organization, architecture, and relevant implementation details.
"""

            result = subprocess.run(
                ["gemini-cli", "prompt", full_prompt.strip()],
                cwd=str(self.base_path),
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                logger.info(f"Codebase investigation completed: {query}")
                return result.stdout.strip()
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"Gemini CLI failed: {error_msg}")
                raise ContextRetrievalError(f"Gemini CLI error: {error_msg}")

        except subprocess.TimeoutExpired as e:
            logger.error(f"Codebase investigation timed out for '{query}'")
            raise ContextRetrievalError("Codebase investigation timed out after 60 seconds") from e
        except FileNotFoundError as e:
            logger.error("Gemini CLI not found - ensure gemini-cli is installed and in PATH")
            raise ContextRetrievalError(
                "Gemini CLI not installed - install from https://github.com/eliben/gemini-cli"
            ) from e
