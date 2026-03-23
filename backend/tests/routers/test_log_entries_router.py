"""Tests for log entries router (POST/GET/PATCH /api/log-entries)."""

import datetime

import pytest

from devboard.db.models.log_entry import LogEntrySource, LogEntryStatus
from devboard.db.repositories.log_entry import LogEntryRepository


@pytest.fixture
def log_entry_repo(db_session):
    """LogEntryRepository bound to the test session."""
    return LogEntryRepository(db_session)


@pytest.fixture
def test_project(db_session):
    """Create a minimal project for log entry scoping."""
    from devboard.db.models.document import DocumentType
    from devboard.db.repositories import DocumentRepository, ProjectRepository

    doc_repo = DocumentRepository(db_session)
    project_repo = ProjectRepository(db_session)

    spec_doc = doc_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(name="Log Entry Test Project", description="", specification=spec_doc)
    db_session.commit()
    return project


class TestPostLogEntry:
    """Tests for POST /api/log-entries."""

    def test_creates_log_entry_with_required_fields(self, client, test_project):
        """POST with minimal fields returns 201 and correct response."""
        payload = {
            "type": "thought",
            "content": "Something I noticed",
            "project_id": test_project.id,
        }
        response = client.post("/api/log-entries/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "thought"
        assert data["content"] == "Something I noticed"
        assert data["source"] == "developer"
        assert data["project_id"] == test_project.id
        assert data["task_id"] is None
        assert data["status"] == "active"
        assert data["pinned"] is False
        assert data["metadata"] is None
        assert "id" in data
        assert "timestamp" in data

    def test_creates_log_entry_with_all_fields(self, client, test_project):
        """POST with all optional fields persists them correctly."""
        payload = {
            "type": "blocker",
            "content": "Can't reproduce the race condition",
            "source": "agent",
            "metadata": {"agent_id": 5, "agent_run_id": 42},
            "project_id": test_project.id,
            "pinned": True,
        }
        response = client.post("/api/log-entries/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "agent"
        assert data["metadata"] == {"agent_id": 5, "agent_run_id": 42}
        assert data["pinned"] is True

    def test_auto_populates_project_id_from_task(self, client, db_session, test_task):
        """POST with task_id only auto-resolves project_id from the task's parent."""
        payload = {
            "type": "blocker",
            "content": "can't reproduce the race condition",
            "task_id": test_task.id,
        }
        response = client.post("/api/log-entries/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == test_task.id
        assert data["project_id"] == test_task.project_id

    def test_invalid_task_id_returns_404(self, client):
        """POST with nonexistent task_id returns 404."""
        payload = {
            "type": "thought",
            "content": "Something",
            "task_id": 999999,
        }
        response = client.post("/api/log-entries/", json=payload)
        assert response.status_code == 404


class TestGetLogEntries:
    """Tests for GET /api/log-entries."""

    def _create_log_entry(self, log_entry_repo, db_session, **kwargs):
        """Helper to create a log entry directly via the repository."""
        defaults = {
            "source": LogEntrySource.DEVELOPER,
            "type": "thought",
            "content": "test log entry",
        }
        defaults.update(kwargs)
        log_entry = log_entry_repo.create(**defaults)
        db_session.commit()
        return log_entry

    def test_returns_empty_list_when_no_log_entries(self, client):
        """GET with no log entries returns empty list."""
        response = client.get("/api/log-entries/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_filter_by_project_id(self, client, log_entry_repo, db_session, test_project):
        """GET filtered by project_id returns only matching log entries."""
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, content="project log entry")
        response = client.get(f"/api/log-entries/?project_id={test_project.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(e["project_id"] == test_project.id for e in data)

    def test_filter_by_task_id(self, client, log_entry_repo, db_session, test_task):
        """GET filtered by task_id returns only matching log entries."""
        self._create_log_entry(log_entry_repo, db_session, task_id=test_task.id, content="task log entry")
        response = client.get(f"/api/log-entries/?task_id={test_task.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(e["task_id"] == test_task.id for e in data)

    def test_filter_by_exact_type(self, client, log_entry_repo, db_session, test_project):
        """GET with exact type filter returns only matching log entries."""
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, type="decision")
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, type="blocker")
        response = client.get(f"/api/log-entries/?project_id={test_project.id}&type=decision")
        assert response.status_code == 200
        data = response.json()
        assert all(e["type"] == "decision" for e in data)

    def test_filter_by_wildcard_type(self, client, log_entry_repo, db_session, test_project):
        """GET with wildcard type pattern (e.g. task.*) matches correctly."""
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, type="task.created")
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, type="task.completed")
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, type="thought")
        response = client.get(f"/api/log-entries/?project_id={test_project.id}&type=task.*")
        assert response.status_code == 200
        data = response.json()
        task_log_entries = [e for e in data if e["type"].startswith("task.")]
        assert len(task_log_entries) >= 2
        assert all(e["type"].startswith("task.") for e in data)

    def test_filter_by_status(self, client, log_entry_repo, db_session, test_project):
        """GET filtered by status returns only matching log entries."""
        active_entry = self._create_log_entry(
            log_entry_repo, db_session, project_id=test_project.id, type="filter_status_test_active"
        )
        resolved_entry = self._create_log_entry(
            log_entry_repo,
            db_session,
            project_id=test_project.id,
            type="filter_status_test_resolved",
            status=LogEntryStatus.RESOLVED,
        )
        _ = active_entry
        _ = resolved_entry
        response = client.get(f"/api/log-entries/?project_id={test_project.id}&status=resolved")
        assert response.status_code == 200
        data = response.json()
        assert all(e["status"] == "resolved" for e in data)

    def test_filter_by_source(self, client, log_entry_repo, db_session, test_project):
        """GET filtered by source returns only matching log entries."""
        self._create_log_entry(
            log_entry_repo, db_session, project_id=test_project.id, type="src_filter_test", source=LogEntrySource.AGENT
        )
        response = client.get(f"/api/log-entries/?project_id={test_project.id}&source=agent")
        assert response.status_code == 200
        data = response.json()
        assert all(e["source"] == "agent" for e in data)

    def test_filter_by_pinned(self, client, log_entry_repo, db_session, test_project):
        """GET filtered by pinned=true returns only pinned log entries."""
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, type="pin_test", pinned=True)
        self._create_log_entry(log_entry_repo, db_session, project_id=test_project.id, type="pin_test_2", pinned=False)
        response = client.get(f"/api/log-entries/?project_id={test_project.id}&pinned=true")
        assert response.status_code == 200
        data = response.json()
        assert all(e["pinned"] is True for e in data)

    def test_filter_by_date_range(self, client, log_entry_repo, db_session, test_project):
        """GET with since/until date range filters log entries correctly."""
        past = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        future = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
        self._create_log_entry(
            log_entry_repo, db_session, project_id=test_project.id, type="date_range_test", timestamp=past
        )
        self._create_log_entry(
            log_entry_repo, db_session, project_id=test_project.id, type="date_range_test", timestamp=future
        )
        response = client.get(
            f"/api/log-entries/?project_id={test_project.id}&type=date_range_test"
            "&since=2019-01-01T00:00:00Z&until=2021-01-01T00:00:00Z"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_pagination(self, client, log_entry_repo, db_session, test_project):
        """GET with limit/offset paginates results."""
        for i in range(5):
            self._create_log_entry(
                log_entry_repo,
                db_session,
                project_id=test_project.id,
                type="pagination_test",
                content=f"log entry {i}",
            )
        first_page = client.get(f"/api/log-entries/?project_id={test_project.id}&type=pagination_test&limit=2&offset=0")
        second_page = client.get(
            f"/api/log-entries/?project_id={test_project.id}&type=pagination_test&limit=2&offset=2"
        )
        assert first_page.status_code == 200
        assert second_page.status_code == 200
        assert len(first_page.json()) == 2
        assert len(second_page.json()) == 2
        first_ids = {e["id"] for e in first_page.json()}
        second_ids = {e["id"] for e in second_page.json()}
        assert first_ids.isdisjoint(second_ids)


class TestPatchLogEntry:
    """Tests for PATCH /api/log-entries/{log_entry_id}."""

    def _create_log_entry(self, log_entry_repo, db_session, **kwargs):
        defaults = {"source": LogEntrySource.DEVELOPER, "type": "thought", "content": "test"}
        defaults.update(kwargs)
        log_entry = log_entry_repo.create(**defaults)
        db_session.commit()
        return log_entry

    def test_update_status(self, client, log_entry_repo, db_session):
        """PATCH updates status and returns updated log entry."""
        log_entry = self._create_log_entry(log_entry_repo, db_session)
        response = client.patch(f"/api/log-entries/{log_entry.id}", json={"status": "resolved"})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == log_entry.id
        assert data["status"] == "resolved"

    def test_update_pinned(self, client, log_entry_repo, db_session):
        """PATCH updates pinned flag and returns updated log entry."""
        log_entry = self._create_log_entry(log_entry_repo, db_session)
        response = client.patch(f"/api/log-entries/{log_entry.id}", json={"pinned": True})
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == log_entry.id
        assert data["pinned"] is True

    def test_update_both_fields(self, client, log_entry_repo, db_session):
        """PATCH with both status and pinned updates both fields."""
        log_entry = self._create_log_entry(log_entry_repo, db_session)
        response = client.patch(f"/api/log-entries/{log_entry.id}", json={"status": "superseded", "pinned": True})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "superseded"
        assert data["pinned"] is True

    def test_returns_404_for_nonexistent_log_entry(self, client):
        """PATCH returns 404 when log entry does not exist."""
        response = client.patch("/api/log-entries/999999", json={"status": "resolved"})
        assert response.status_code == 404

    def test_returns_422_when_no_fields_provided(self, client, log_entry_repo, db_session):
        """PATCH returns 422 when neither status nor pinned is provided."""
        log_entry = self._create_log_entry(log_entry_repo, db_session)
        response = client.patch(f"/api/log-entries/{log_entry.id}", json={})
        assert response.status_code == 422
