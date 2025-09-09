"""Tests for codebases router."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from devboard.db.models import Codebase
from devboard.db.repositories import CodebaseRepository
from devboard.utils.hash import compute_content_hash


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_git_dir():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        # Create a test file and commit it
        test_file = Path(temp_dir) / "README.md"
        test_file.write_text("# Test Repository")
        subprocess.run(["git", "add", "README.md"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True, capture_output=True
        )

        # Add a remote origin
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        yield temp_dir


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
        """Test creating a new codebase from a non-git directory."""
        response = client.post("/api/codebases/", json=test_codebase_data)
        assert response.status_code == 200

        codebase_data = response.json()
        assert codebase_data["name"] == test_codebase_data["name"]
        assert codebase_data["local_path"] == test_codebase_data["local_path"]
        assert codebase_data["description"] == test_codebase_data["description"]
        assert codebase_data["repository_url"] is None  # No git repo detected
        assert "id" in codebase_data

    def test_create_codebase_with_git(self, client, temp_git_dir):
        """Test creating a new codebase from a git directory."""
        codebase_data = {
            "name": "Git Test Codebase",
            "local_path": temp_git_dir,
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

    def test_get_architecture_document_not_exists(self, client, db_session, test_codebase_data):
        """Test getting architecture document when file doesn't exist."""
        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        response = client.get(f"/api/codebases/{created_codebase.id}/architecture_document/")
        assert response.status_code == 200

        data = response.json()
        assert data["exists"] is False
        assert data["content"] is None
        assert data["content_hash"] is None

    def test_get_architecture_document_exists(self, client, db_session, test_codebase_data):
        """Test getting architecture document when file exists."""
        # Create test codebase with architecture document
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Create architecture document
        arch_file = Path(test_codebase_data["local_path"]) / "ARCHITECTURE.md"
        arch_content = "# Architecture\n\nThis is the architecture document."
        arch_file.write_text(arch_content)

        response = client.get(f"/api/codebases/{created_codebase.id}/architecture_document/")
        assert response.status_code == 200

        data = response.json()
        assert data["exists"] is True
        assert data["content"] == arch_content
        assert data["content_hash"] is not None
        assert data["content_hash"].startswith("sha256:")  # SHA256 hash with prefix

    def test_update_architecture_document_new(self, client, db_session, test_codebase_data):
        """Test creating a new architecture document."""
        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        new_content = "# New Architecture\n\nThis is a new architecture document."
        update_data = {
            "content": new_content,
            "original_hash": None
        }

        response = client.put(
            f"/api/codebases/{created_codebase.id}/architecture_document/",
            json=update_data
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["content_hash"] is not None

        # Verify file was created
        arch_file = Path(test_codebase_data["local_path"]) / "ARCHITECTURE.md"
        assert arch_file.exists()
        assert arch_file.read_text() == new_content

    def test_update_architecture_document_existing_success(self, client, db_session, test_codebase_data):
        """Test updating existing architecture document with correct hash."""
        # Create test codebase with existing architecture document
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Create initial architecture document
        arch_file = Path(test_codebase_data["local_path"]) / "ARCHITECTURE.md"
        original_content = "# Original Architecture\n\nOriginal content."
        arch_file.write_text(original_content)

        # Get current hash
        original_hash = compute_content_hash(original_content)

        # Update with new content
        new_content = "# Updated Architecture\n\nUpdated content."
        update_data = {
            "content": new_content,
            "original_hash": original_hash
        }

        response = client.put(
            f"/api/codebases/{created_codebase.id}/architecture_document/",
            json=update_data
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["content_hash"] is not None
        assert data["content_hash"] != original_hash

        # Verify file was updated
        assert arch_file.read_text() == new_content

    def test_update_architecture_document_conflict(self, client, db_session, test_codebase_data):
        """Test updating architecture document with hash conflict."""
        # Create test codebase with existing architecture document
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Create initial architecture document
        arch_file = Path(test_codebase_data["local_path"]) / "ARCHITECTURE.md"
        original_content = "# Original Architecture\n\nOriginal content."
        arch_file.write_text(original_content)

        # Update the file externally (simulating conflict)
        modified_content = "# Externally Modified Architecture\n\nExternally modified."
        arch_file.write_text(modified_content)

        # Try to update with old hash
        new_content = "# User Updated Architecture\n\nUser updated content."
        update_data = {
            "content": new_content,
            "original_hash": "wrong_hash"
        }

        response = client.put(
            f"/api/codebases/{created_codebase.id}/architecture_document/",
            json=update_data
        )
        assert response.status_code == 409

        data = response.json()
        assert "modified by another process" in data["detail"]["message"].lower()
        # Conflict response includes current_hash for retry
        assert "current_hash" in data["detail"]

        # Verify file wasn't changed
        assert arch_file.read_text() == modified_content

    @patch('devboard.services.codebase_investigation.execute_gemini_prompt', new_callable=AsyncMock)
    def test_generate_architecture_document(self, mock_gemini_prompt, client, db_session, test_codebase_data):
        """Test generating architecture document via AI."""
        # Mock the Gemini CLI response
        mock_architecture_content = """# Architecture Overview: Test Codebase

## High-Level Summary
A simple Python codebase with a main module and utility functions.

## Key Components
- main.py: Entry point with main() function
- utils.py: Helper utilities with helper() function
"""
        mock_gemini_prompt.return_value = mock_architecture_content

        # Create test codebase
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(**test_codebase_data)
        created_codebase = codebase_repo.create(codebase)
        db_session.commit()

        # Create some source files for analysis
        src_dir = Path(test_codebase_data["local_path"]) / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def main():\n    pass")
        (src_dir / "utils.py").write_text("def helper():\n    pass")

        response = client.post(f"/api/codebases/{created_codebase.id}/architecture_document/generate")

        # This should work with mocked gemini response
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["file_path"] is not None

        # Verify architecture file was created with mocked content
        arch_file = Path(test_codebase_data["local_path"]) / "ARCHITECTURE.md"
        assert arch_file.exists()
        assert "Test Codebase" in arch_file.read_text()

        # Verify the mock was called
        mock_gemini_prompt.assert_called_once()

    def test_get_architecture_document_nonexistent_codebase(self, client):
        """Test getting architecture document for non-existent codebase."""
        response = client.get("/api/codebases/999/architecture_document/")
        assert response.status_code == 404
        assert response.json()["detail"] == "Codebase not found"

    def test_update_architecture_document_nonexistent_codebase(self, client):
        """Test updating architecture document for non-existent codebase."""
        update_data = {
            "content": "# Test",
            "original_hash": None
        }
        response = client.put("/api/codebases/999/architecture_document/", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Codebase not found"
