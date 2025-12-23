"""Tests for documents API endpoints."""


class TestDocumentsRouter:
    """Tests for /api/documents endpoints."""

    def test_get_document(self, client, test_task):
        """GET /documents/{id} should return document with content."""
        # Get the specification document from the test task
        doc_id = test_task.specification.id

        response = client.get(f"/api/documents/{doc_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == doc_id
        assert "content" in data
        assert data["content"] == "Test task specification"
        assert "content_hash" in data
        assert "document_type" in data
        assert data["document_type"] == "task_specification"
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_document_not_found(self, client):
        """GET /documents/{id} should return 404 for non-existent document."""
        response = client.get("/api/documents/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestTaskResponseDocumentIds:
    """Tests for task endpoints returning document IDs."""

    def test_get_task_returns_document_ids(self, client, test_task):
        """GET /tasks/{id} should return document IDs (not full content)."""
        response = client.get(f"/api/tasks/{test_task.id}")
        assert response.status_code == 200

        data = response.json()

        # Should have document IDs
        assert "specification_document_id" in data
        assert data["specification_document_id"] == test_task.specification.id
        assert "implementation_plan_document_id" in data
        assert data["implementation_plan_document_id"] is None  # No implementation plan yet

        # Should NOT have full document objects
        assert "specification" not in data
        assert "implementation_plan" not in data


class TestProjectResponseDocumentIds:
    """Tests for project endpoints returning document IDs."""

    def test_get_project_returns_document_id(self, client, test_task):
        """GET /projects/{id} should return document ID (not full content)."""
        # Get the project ID from the task
        project_id = test_task.project_id

        response = client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200

        data = response.json()

        # Should have document ID
        assert "specification_document_id" in data
        assert isinstance(data["specification_document_id"], int)

        # Should NOT have full document object
        assert "specification" not in data
