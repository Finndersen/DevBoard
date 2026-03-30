"""Tests for codebases router."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from devboard.db.models import Codebase
from devboard.db.repositories import CodebaseRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_git_repo():
    """Mock GitRepoIntegration for a valid git repo with a remote."""
    with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.detect_git_remote_url = AsyncMock(return_value="https://github.com/test/repo.git")
        mock_instance.has_commits = AsyncMock(return_value=True)
        mock_instance.get_default_branch = AsyncMock(return_value="main")
        yield mock_cls


@pytest.fixture
def test_codebase_data(temp_dir):
    """Sample codebase data for testing."""
    return {
        "name": "Test Codebase",
        "local_path": temp_dir,
        "description": "A test codebase for unit testing",
        "repository_url": None,  # For direct model creation
    }


class TestCodebasesRouter:
    """Test codebases router endpoints."""

    def test_list_codebases_empty(self, client):
        """Test listing codebases when none exist."""
        response = client.get("/api/codebases/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_codebases_with_data(self, client, db_session, test_codebase_data):
        """Test listing codebases with existing data."""
        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        response = client.get("/api/codebases/")
        assert response.status_code == 200
        codebases = response.json()
        assert len(codebases) == 1
        assert codebases[0]["name"] == test_codebase_data["name"]
        assert codebases[0]["id"] == created_codebase.id

    def test_create_codebase_non_git(self, client, test_codebase_data):
        """Test creating a new codebase from a non-git directory fails."""
        response = client.post("/api/codebases/", json=test_codebase_data)
        assert response.status_code == 400
        assert "no commits" in response.json()["detail"]

    def test_create_codebase_with_git(self, client, temp_dir, mock_git_repo):
        """Test creating a new codebase from a git directory."""
        codebase_data = {
            "name": "Git Test Codebase",
            "local_path": temp_dir,
            "description": "A test codebase with git repository",
        }

        response = client.post("/api/codebases/", json=codebase_data)
        assert response.status_code == 200

        result = response.json()
        assert result["name"] == codebase_data["name"]
        assert result["local_path"] == codebase_data["local_path"]
        assert result["description"] == codebase_data["description"]
        assert result["repository_url"] == "https://github.com/test/repo.git"  # Auto-detected
        assert "id" in result

    def test_create_codebase_creates_main_repo_slot(self, client, db_session, temp_dir, mock_git_repo):
        """Test that creating a codebase also creates a main repo worktree slot."""
        codebase_data = {
            "name": "Git Test Codebase",
            "local_path": temp_dir,
            "description": "A test codebase with git repository",
        }

        response = client.post("/api/codebases/", json=codebase_data)
        assert response.status_code == 200

        result = response.json()
        codebase_id = result["id"]

        # Verify main repo slot was created
        worktree_slot_repo = WorktreeSlotRepository(db_session)
        slots = worktree_slot_repo.get_by_codebase(codebase_id, include_main=True)

        assert len(slots) == 1
        main_slot = slots[0]
        assert main_slot.is_main_repo is True
        assert main_slot.path == temp_dir
        assert main_slot.codebase_id == codebase_id

    def test_create_codebase_invalid_path(self, client):
        """Test creating a codebase with an invalid local path."""
        invalid_data = {
            "name": "Invalid Codebase",
            "local_path": "/nonexistent/path",
            "description": "This should fail",
        }

        response = client.post("/api/codebases/", json=invalid_data)
        assert response.status_code == 400
        assert "Local path does not exist" in response.json()["detail"]

    def test_create_codebase_file_not_directory(self, client, temp_dir):
        """Test creating a codebase with a file path instead of directory."""
        # Create a test file
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("test content")

        invalid_data = {
            "name": "File Codebase",
            "local_path": str(test_file),
            "description": "This should fail - it's a file",
        }

        response = client.post("/api/codebases/", json=invalid_data)
        assert response.status_code == 400
        assert "Local path is not a directory" in response.json()["detail"]

    def test_get_codebase_success(self, client, db_session, test_codebase_data):
        """Test getting a specific codebase."""
        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        response = client.get(f"/api/codebases/{created_codebase.id}")
        assert response.status_code == 200

        codebase_data = response.json()
        assert codebase_data["name"] == test_codebase_data["name"]
        assert codebase_data["id"] == created_codebase.id

    def test_get_codebase_not_found(self, client):
        """Test getting a non-existent codebase."""
        response = client.get("/api/codebases/999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Codebase not found"

    def test_delete_codebase_success(self, client, db_session, test_codebase_data):
        """Test deleting a codebase."""
        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        response = client.delete(f"/api/codebases/{created_codebase.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Codebase deleted successfully"
