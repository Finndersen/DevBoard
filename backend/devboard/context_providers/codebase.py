"""Codebase context provider for file and repository context using AI analysis."""

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from devboard.integrations.codebase import CodebaseIntegration

from .base import (
    BaseContextProvider,
    ContextRetrievalError,
    ContextStrategy,
    DescriptionGenerationError,
    ResourceHandlingError,
)

logger = logging.getLogger(__name__)


class CodebaseContextProvider(BaseContextProvider):
    """Context provider for codebase resources using AI-powered code analysis."""

    provider_type = "codebase"

    def __init__(self, integration: CodebaseIntegration):
        """Initialize with Codebase integration."""
        self.integration = integration

    def can_handle_uri(self, resource_uri: str) -> bool:
        """Check if URI is a codebase resource (file path or file:// URL)."""
        try:
            # Handle file:// URLs, absolute paths, or relative paths
            if resource_uri.startswith("file://"):
                return True
            elif resource_uri.startswith("/"):
                return True
            elif not urlparse(resource_uri).scheme:
                # Relative path or filename
                return True
            return False
        except Exception:
            return False

    def get_retrieval_strategy(self, resource_uri: str) -> ContextStrategy:
        """Determine strategy based on resource type.

        Single files are EAGER (small-scope), directories are ON_DEMAND (large-scope).
        """
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        normalized_path = self._normalize_file_path(resource_uri)
        full_path = Path(self.integration.repo_path) / normalized_path

        # Single files are EAGER, directories are ON_DEMAND
        if full_path.is_file():
            return ContextStrategy.EAGER
        else:
            return ContextStrategy.ON_DEMAND

    def _normalize_file_path(self, resource_uri: str) -> str:
        """Normalize resource URI to a relative file path."""
        try:
            if resource_uri.startswith("file://"):
                # Remove file:// prefix and convert to relative path
                file_path = resource_uri[7:]
                return self.integration.parse_file_url(file_path) or file_path
            elif resource_uri.startswith("/"):
                # Absolute path - convert to relative
                return self.integration.parse_file_url(resource_uri) or resource_uri
            else:
                # Assume relative path
                return resource_uri
        except Exception:
            return resource_uri

    async def get_resource(self, resource_uri: str) -> dict[str, Any]:
        """Get full resource data for EAGER strategy (not typically used for codebase)."""
        if not self.can_handle_uri(resource_uri):
            raise ResourceHandlingError(f"Cannot handle URI: {resource_uri}")

        try:
            file_path = self._normalize_file_path(resource_uri)

            # Get file content and metadata
            content = await self.integration.read_file(file_path)
            file_info = await self.integration.get_file_info(file_path)

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
            try:
                full_path = Path(self.integration.repo_path) / file_path
                if full_path.is_file():
                    # Specific file - use AI to analyze file content with query context
                    analysis_context = f"""
File: {file_path}
Query: {query}

Please analyze this specific file and provide insights relevant to the query.
Focus on the implementation details, patterns, and relationships within this file.
"""
                    return await self.integration.investigate_codebase(query, analysis_context)

                elif full_path.is_dir():
                    # Directory - use AI to analyze directory structure and contents
                    analysis_context = f"""
Directory: {file_path}
Query: {query}

Please analyze this directory structure and its contents.
Focus on the overall organization, key files, and architectural patterns.
"""
                    return await self.integration.investigate_codebase(query, analysis_context)

                else:
                    # Pattern or general codebase query
                    analysis_context = f"""
Codebase Pattern/Query: {file_path}
Query: {query}

Please search and analyze the codebase for patterns, implementations, or concepts related to this query.
"""
                    return await self.integration.investigate_codebase(query, analysis_context)

            except Exception:
                # Fallback to general investigation
                return await self.integration.investigate_codebase(
                    f"{query} (related to: {file_path})"
                )

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

            try:
                full_path = Path(self.integration.repo_path) / file_path
                if full_path.is_file():
                    # Get file info and generate description
                    file_info = await self.integration.get_file_info(file_path)
                    file_size = file_info.get("size", 0)

                    # Try to determine file type from extension
                    suffix = full_path.suffix
                    if suffix in [".py", ".js", ".ts", ".java", ".cpp", ".c"]:
                        return f"Code file: {file_path} ({suffix[1:].upper()}, {file_size} bytes)"
                    elif suffix in [".md", ".txt", ".rst"]:
                        return (
                            f"Documentation: {file_path} ({suffix[1:].upper()}, {file_size} bytes)"
                        )
                    elif suffix in [".json", ".yaml", ".yml", ".toml"]:
                        return (
                            f"Configuration: {file_path} ({suffix[1:].upper()}, {file_size} bytes)"
                        )
                    else:
                        return f"File: {file_path} ({file_size} bytes)"

                elif full_path.is_dir():
                    # Count files in directory
                    try:
                        files = await self.integration.list_files(file_path)
                        return f"Directory: {file_path} ({len(files)} files)"
                    except Exception:
                        return f"Directory: {file_path}"
                else:
                    return f"Codebase pattern: {file_path}"

            except Exception:
                return f"Codebase resource: {file_path}"

        except Exception as e:
            if isinstance(e, ResourceHandlingError | DescriptionGenerationError):
                raise
            logger.error(f"Error generating codebase description for {resource_uri}: {e}")
            raise DescriptionGenerationError(f"Failed to generate codebase description: {e}") from e
