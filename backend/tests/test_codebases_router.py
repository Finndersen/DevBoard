"""Tests for codebases router."""

import pytest
from fastapi.testclient import TestClient

from devboard.db.models import Codebase
from devboard.main import app
from devboard.repositories.codebase import CodebaseRepository


@pytest.fixture
def client(db_session):
    """FastAPI test client with database setup."""
    from devboard.db.database import get_db

    def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_codebase_data():
    """Sample codebase data for testing."""
    return {
        "name": "Test Codebase",
        "local_path": "/path/to/test/codebase",
        "description": "A test codebase for unit testing",
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

    def test_create_codebase(self, client, test_codebase_data):
        """Test creating a new codebase."""
        response = client.post("/api/codebases/", json=test_codebase_data)
        assert response.status_code == 200

        codebase_data = response.json()
        assert codebase_data["name"] == test_codebase_data["name"]
        assert codebase_data["local_path"] == test_codebase_data["local_path"]
        assert codebase_data["description"] == test_codebase_data["description"]
        assert "id" in codebase_data

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
