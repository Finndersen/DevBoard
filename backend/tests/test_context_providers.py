"""Tests for context providers."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from devboard.context_providers.base import (
    BaseContextProvider,
    ContextProviderRegistry,
    ContextRetrievalError,
    ContextStrategy,
    ResourceHandlingError,
)
from devboard.context_providers.codebase import CodebaseContextProvider
from devboard.context_providers.github import GitHubContextProvider
from devboard.context_providers.jira import JiraContextProvider
from devboard.context_providers.slack import SlackContextProvider
from devboard.context_providers.webpage import WebPageContextProvider


class TestContextProviderRegistry:
    """Test the context provider registry."""

    def setup_method(self):
        """Clear registry before each test."""
        ContextProviderRegistry.clear()

    def test_register_and_get_provider(self):
        """Test registering and retrieving providers."""
        mock_provider = Mock(spec=BaseContextProvider)
        mock_provider.provider_type = "test"

        ContextProviderRegistry.register("test", mock_provider)

        assert ContextProviderRegistry.get("test") == mock_provider
        assert ContextProviderRegistry.get("nonexistent") is None

    def test_list_available_providers(self):
        """Test listing available providers."""
        mock_provider1 = Mock(spec=BaseContextProvider)
        mock_provider1.provider_type = "test1"
        mock_provider2 = Mock(spec=BaseContextProvider)
        mock_provider2.provider_type = "test2"

        ContextProviderRegistry.register("test1", mock_provider1)
        ContextProviderRegistry.register("test2", mock_provider2)

        available = ContextProviderRegistry.list_available()
        assert set(available) == {"test1", "test2"}

    def test_get_provider_for_uri(self):
        """Test finding provider by URI."""
        mock_provider = Mock(spec=BaseContextProvider)
        mock_provider.can_handle_uri.return_value = True

        ContextProviderRegistry.register("test", mock_provider)

        provider = ContextProviderRegistry.get_provider_for_uri("test://resource")
        assert provider == mock_provider
        mock_provider.can_handle_uri.assert_called_once_with("test://resource")

    def test_get_provider_for_uri_not_found(self):
        """Test URI with no matching provider."""
        mock_provider = Mock(spec=BaseContextProvider)
        mock_provider.can_handle_uri.return_value = False

        ContextProviderRegistry.register("test", mock_provider)

        provider = ContextProviderRegistry.get_provider_for_uri("unknown://resource")
        assert provider is None


class TestGitHubContextProvider:
    """Test GitHub context provider."""

    @pytest.fixture
    def mock_integration(self):
        """Mock GitHub integration."""
        integration = Mock()
        integration.get_pull_request = AsyncMock()
        integration.get_issue = AsyncMock()
        integration.get_commit = AsyncMock()
        integration.get_file_content = AsyncMock()
        return integration

    @pytest.fixture
    def provider(self, mock_integration):
        """GitHub context provider with mocked integration."""
        return GitHubContextProvider(mock_integration)

    def test_can_handle_uri(self, provider):
        """Test URI handling detection."""
        assert provider.can_handle_uri("https://github.com/owner/repo/pull/123")
        assert provider.can_handle_uri("https://github.com/owner/repo/issues/456")
        assert provider.can_handle_uri("https://github.com/owner/repo/commit/abc123")
        assert not provider.can_handle_uri("https://gitlab.com/owner/repo")
        assert not provider.can_handle_uri("invalid-url")

    def test_get_retrieval_strategy(self, provider):
        """Test strategy determination."""
        # Small-scope resources should be EAGER
        assert (
            provider.get_retrieval_strategy("https://github.com/owner/repo/pull/123")
            == ContextStrategy.EAGER
        )
        assert (
            provider.get_retrieval_strategy("https://github.com/owner/repo/issues/456")
            == ContextStrategy.EAGER
        )
        assert (
            provider.get_retrieval_strategy("https://github.com/owner/repo/commit/abc123")
            == ContextStrategy.EAGER
        )

        # Large-scope resources should be ON_DEMAND
        assert (
            provider.get_retrieval_strategy("https://github.com/owner/repo")
            == ContextStrategy.ON_DEMAND
        )

    def test_get_retrieval_strategy_invalid_uri(self, provider):
        """Test strategy with invalid URI."""
        with pytest.raises(ResourceHandlingError):
            provider.get_retrieval_strategy("https://gitlab.com/owner/repo")

    @pytest.mark.asyncio
    async def test_get_resource_pull_request(self, provider, mock_integration):
        """Test getting PR resource data."""
        mock_integration.get_pull_request.return_value = {"id": 123, "title": "Test PR"}

        result = await provider.get_resource("https://github.com/owner/repo/pull/123")

        assert result["type"] == "pull_request"
        assert result["data"] == {"id": 123, "title": "Test PR"}
        assert result["uri"] == "https://github.com/owner/repo/pull/123"
        mock_integration.get_pull_request.assert_called_once_with("owner", "repo", 123)

    @pytest.mark.asyncio
    async def test_get_resource_invalid_uri(self, provider):
        """Test get_resource with invalid URI."""
        with pytest.raises(ResourceHandlingError):
            await provider.get_resource("https://gitlab.com/owner/repo")

    @pytest.mark.asyncio
    async def test_generate_resource_description(self, provider, mock_integration):
        """Test generating resource descriptions."""
        mock_integration.get_pull_request.return_value = {
            "title": "Fix authentication bug",
            "body": "This PR fixes a critical auth issue",
        }

        description = await provider.generate_resource_description(
            "https://github.com/owner/repo/pull/123"
        )

        assert "Fix authentication bug" in description
        assert "pr" in description.lower()


class TestJiraContextProvider:
    """Test Jira context provider."""

    @pytest.fixture
    def mock_integration(self):
        """Mock Jira integration."""
        integration = Mock()
        integration.get_issue.return_value = {"key": "TEST-123", "summary": "Test issue"}
        integration.parse_issue_url.return_value = {"issue_key": "TEST-123"}
        return integration

    @pytest.fixture
    def provider(self, mock_integration):
        """Jira context provider with mocked integration."""
        return JiraContextProvider(mock_integration)

    def test_can_handle_uri(self, provider):
        """Test URI handling detection."""
        assert provider.can_handle_uri("https://company.atlassian.net/browse/PROJ-123")
        assert not provider.can_handle_uri("https://github.com/owner/repo")

    def test_get_retrieval_strategy(self, provider):
        """Test strategy determination."""
        # Single issues should be EAGER
        assert (
            provider.get_retrieval_strategy("https://company.atlassian.net/browse/PROJ-123")
            == ContextStrategy.EAGER
        )

        # Projects should be ON_DEMAND
        assert (
            provider.get_retrieval_strategy("https://company.atlassian.net/projects/PROJ")
            == ContextStrategy.ON_DEMAND
        )


class TestSlackContextProvider:
    """Test Slack context provider."""

    @pytest.fixture
    def mock_integration(self):
        """Mock Slack integration."""
        integration = Mock()
        integration.get_message.return_value = {"text": "Test message", "user": "U123"}
        return integration

    @pytest.fixture
    def provider(self, mock_integration):
        """Slack context provider with mocked integration."""
        return SlackContextProvider(mock_integration)

    def test_can_handle_uri(self, provider):
        """Test URI handling detection."""
        assert provider.can_handle_uri("https://company.slack.com/archives/C123/p123456")
        assert provider.can_handle_uri("https://company.slack.com/archives/C123")
        assert not provider.can_handle_uri("https://discord.com/channels/123")

    def test_get_retrieval_strategy(self, provider):
        """Test strategy determination."""
        # Single messages should be EAGER
        assert (
            provider.get_retrieval_strategy("https://company.slack.com/archives/C123/p123456")
            == ContextStrategy.EAGER
        )

        # Channels should be ON_DEMAND
        assert (
            provider.get_retrieval_strategy("https://company.slack.com/archives/C123")
            == ContextStrategy.ON_DEMAND
        )


class TestCodebaseContextProvider:
    """Test Codebase context provider."""

    @pytest.fixture
    def mock_integration(self):
        """Mock Codebase integration."""
        integration = Mock()
        integration.repo_path = "/test/repo"
        integration.read_file = AsyncMock(return_value="file content")
        integration.get_file_info = AsyncMock(return_value={"size": 100})
        integration.investigate_codebase = AsyncMock(return_value="Analysis result")
        return integration

    @pytest.fixture
    def provider(self, mock_integration):
        """Codebase context provider with mocked integration."""
        return CodebaseContextProvider(mock_integration)

    def test_can_handle_uri(self, provider):
        """Test URI handling detection."""
        assert provider.can_handle_uri("/path/to/file.py")
        assert provider.can_handle_uri("file:///absolute/path/file.py")
        assert provider.can_handle_uri("src/main.py")
        assert not provider.can_handle_uri("https://github.com/owner/repo")

    @patch("pathlib.Path.is_file")
    def test_get_retrieval_strategy_file(self, mock_is_file, provider):
        """Test strategy for single files (EAGER)."""
        mock_is_file.return_value = True

        strategy = provider.get_retrieval_strategy("src/main.py")
        assert strategy == ContextStrategy.EAGER

    @patch("pathlib.Path.is_file")
    def test_get_retrieval_strategy_directory(self, mock_is_file, provider):
        """Test strategy for directories (ON_DEMAND)."""
        mock_is_file.return_value = False

        strategy = provider.get_retrieval_strategy("src/")
        assert strategy == ContextStrategy.ON_DEMAND

    @pytest.mark.asyncio
    async def test_get_resource(self, provider, mock_integration):
        """Test getting file resource data."""
        result = await provider.get_resource("src/main.py")

        assert result["content"] == "file content"
        assert result["file_info"] == {"size": 100}
        assert result["uri"] == "src/main.py"
        mock_integration.read_file.assert_called_once()
        mock_integration.get_file_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_relevant_context(self, provider, mock_integration):
        """Test getting relevant context via AI analysis."""
        result = await provider.get_relevant_context("src/", "What functions are defined?")

        assert result == "Analysis result"
        mock_integration.investigate_codebase.assert_called_once()


class TestWebPageContextProvider:
    """Test Web Page context provider."""

    @pytest.fixture
    def provider(self):
        """Web page context provider."""
        return WebPageContextProvider(max_content_length=1000)

    def test_can_handle_uri(self, provider):
        """Test URI handling detection."""
        # Should handle any http/https web pages
        assert provider.can_handle_uri("https://example.com/page")
        assert provider.can_handle_uri("http://docs.python.org/guide")
        assert provider.can_handle_uri("https://blog.example.com/post/123")
        assert provider.can_handle_uri(
            "https://github.com/owner/repo"
        )  # Registry priority handles this
        assert provider.can_handle_uri("https://company.atlassian.net/browse/PROJ-123")

        # Should not handle non-web protocols
        assert not provider.can_handle_uri("file:///local/file.txt")
        assert not provider.can_handle_uri("ftp://server.com/file")
        assert not provider.can_handle_uri("invalid-url")

    def test_get_retrieval_strategy(self, provider):
        """Test strategy determination."""
        # All web pages should be EAGER
        assert provider.get_retrieval_strategy("https://example.com/page") == ContextStrategy.EAGER
        assert (
            provider.get_retrieval_strategy("http://docs.python.org/guide") == ContextStrategy.EAGER
        )

    def test_get_retrieval_strategy_invalid_uri(self, provider):
        """Test strategy with invalid URI."""
        with pytest.raises(ResourceHandlingError):
            provider.get_retrieval_strategy("ftp://server.com/file")

    @pytest.mark.asyncio
    async def test_get_resource_success(self, provider):
        """Test successful web page resource retrieval."""
        # Mock the HTTP response
        html_content = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <script>alert('remove me');</script>
                <main>
                    <h1>Main Content</h1>
                    <p>This is the main content of the page.</p>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await provider.get_resource("https://example.com/test")

            assert result["type"] == "webpage"
            assert result["uri"] == "https://example.com/test"
            assert result["title"] == "Test Page"
            assert "Main Content" in result["content"]
            assert "This is the main content" in result["content"]
            assert "alert('remove me')" not in result["content"]  # Script should be removed
            assert "Footer content" not in result["content"]  # Footer should be removed
            assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_get_resource_http_error(self, provider):
        """Test web page retrieval with HTTP error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.HTTPStatusError("404 Not Found", request=Mock(), response=Mock())
            )

            with pytest.raises(ContextRetrievalError):
                await provider.get_resource("https://example.com/notfound")

    @pytest.mark.asyncio
    async def test_generate_resource_description(self, provider):
        """Test generating resource descriptions."""
        html_content = """
        <html>
            <head><title>Example Documentation</title></head>
            <body>
                <main>
                    <p>This is a documentation page about Python programming.</p>
                </main>
            </body>
        </html>
        """

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/html"}
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            description = await provider.generate_resource_description("https://example.com/docs")

            assert "Example Documentation" in description
            assert "Web page:" in description
            assert "words)" in description
