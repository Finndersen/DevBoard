"""Tests for global context API endpoints."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_devboard_home(tmp_path):
    """Redirect get_devboard_home() to tmp_path so tests don't touch the real filesystem."""
    with patch("devboard.services.global_context_service.get_devboard_home", return_value=tmp_path):
        yield tmp_path


class TestGetGlobalContext:
    def test_returns_empty_content_when_file_missing(self, client):
        """GET returns empty content and a hash when no file exists yet."""
        response = client.get("/api/global-context/")
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == ""
        assert isinstance(data["content_hash"], str)
        assert len(data["content_hash"]) == 32  # MD5 hex digest
        assert "updated_at" in data

    def test_returns_file_content_when_file_exists(self, client, mock_devboard_home):
        """GET returns the content of the existing global context file."""
        docs_dir = mock_devboard_home / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "global_context.md").write_text("# My Context\n\nSome domain knowledge.", encoding="utf-8")

        response = client.get("/api/global-context/")
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "# My Context\n\nSome domain knowledge."
        assert isinstance(data["content_hash"], str)
        assert len(data["content_hash"]) == 32


class TestUpdateGlobalContext:
    def test_put_writes_content_and_returns_updated_data(self, client):
        """PUT writes the content to file and returns the updated GlobalContextResponse."""
        new_content = "# Global Context\n\nThis is the global domain context."
        response = client.put("/api/global-context/", json={"content": new_content})
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == new_content
        assert isinstance(data["content_hash"], str)
        assert len(data["content_hash"]) == 32
        assert "updated_at" in data

    def test_put_then_get_returns_updated_content(self, client):
        """After a PUT, a subsequent GET returns the same content."""
        content = "Domain: e-commerce platform\nStack: Python + React"
        client.put("/api/global-context/", json={"content": content})

        response = client.get("/api/global-context/")
        assert response.status_code == 200
        assert response.json()["content"] == content

    def test_put_overwrites_existing_content(self, client, mock_devboard_home):
        """PUT replaces existing file content."""
        docs_dir = mock_devboard_home / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "global_context.md").write_text("Old content", encoding="utf-8")

        response = client.put("/api/global-context/", json={"content": "New content"})
        assert response.status_code == 200
        assert response.json()["content"] == "New content"

        # Verify via GET as well
        get_response = client.get("/api/global-context/")
        assert get_response.json()["content"] == "New content"

    def test_put_creates_docs_directory_if_missing(self, client, mock_devboard_home):
        """PUT creates the docs/ subdirectory if it doesn't exist."""
        docs_dir = mock_devboard_home / "docs"
        assert not docs_dir.exists()

        response = client.put("/api/global-context/", json={"content": "Hello"})
        assert response.status_code == 200
        assert docs_dir.exists()
        assert (docs_dir / "global_context.md").read_text(encoding="utf-8") == "Hello"
