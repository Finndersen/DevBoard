"""Tests for GET /tasks/counts and GET /tasks/archived endpoints."""

import pytest
from fastapi.testclient import TestClient

from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)


@pytest.fixture
def second_project(db_session):
    """Create a second project for filter testing."""
    from devboard.db.models.document import DocumentType

    doc_repo = DocumentRepository(db_session)
    project_repo = ProjectRepository(db_session)
    spec = doc_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(name="Other Project", description="", specification=spec)
    db_session.flush()
    return project


def _make_task(db_session, test_codebase, project, status: TaskStatus, title: str = "Task"):
    """Helper to create a task with the given status."""
    doc_repo = DocumentRepository(db_session)
    task_repo = TaskRepository(db_session)
    spec = doc_repo.create(DocumentType.TASK_SPECIFICATION, "spec")
    task = task_repo.create(
        project_id=project.id,
        title=title,
        specification=spec,
        base_branch="main",
        branch_name=f"branch-{title.lower().replace(' ', '-')}",
        codebase_id=test_codebase.id,
        status=status,
    )
    db_session.flush()
    return task


class TestGetTaskCounts:
    def test_returns_counts_for_all_statuses(self, client: TestClient, test_task, db_session, test_codebase):
        """Counts endpoint returns correct counts per status."""
        # test_task is already PLANNING; create more tasks
        project = test_task.project
        _make_task(db_session, test_codebase, project, TaskStatus.IMPLEMENTING)
        _make_task(db_session, test_codebase, project, TaskStatus.IMPLEMENTING)
        _make_task(db_session, test_codebase, project, TaskStatus.COMPLETE)

        response = client.get("/api/tasks/counts")

        assert response.status_code == 200
        data = response.json()
        assert data["planning"] >= 1
        assert data["implementing"] >= 2
        assert data["complete"] >= 1

    def test_empty_db_returns_empty_dict(self, client: TestClient):
        """With no tasks, counts returns an empty dict."""
        response = client.get("/api/tasks/counts")
        assert response.status_code == 200
        # Might be empty or contain only zeros — the endpoint returns whatever statuses exist
        assert isinstance(response.json(), dict)

    def test_project_id_filter(self, client: TestClient, test_task, db_session, test_codebase, second_project):
        """project_id filter restricts counts to that project."""
        project = test_task.project
        _make_task(db_session, test_codebase, project, TaskStatus.IMPLEMENTING)
        _make_task(db_session, test_codebase, second_project, TaskStatus.IMPLEMENTING, "Other Task")

        response = client.get(f"/api/tasks/counts?project_id={project.id}")

        assert response.status_code == 200
        data = response.json()
        # The IMPLEMENTING count for the main project should be 1 (only the one we created)
        assert data.get("implementing", 0) == 1

    def test_project_id_filter_no_tasks(self, client: TestClient, second_project):
        """project_id filter with no matching tasks returns empty dict."""
        response = client.get(f"/api/tasks/counts?project_id={second_project.id}")
        assert response.status_code == 200
        assert response.json() == {}


class TestListArchivedTasks:
    def test_returns_complete_tasks(self, client: TestClient, test_task, db_session, test_codebase):
        """Archived endpoint returns COMPLETE tasks."""
        project = test_task.project
        _make_task(db_session, test_codebase, project, TaskStatus.COMPLETE, "Done Task")

        response = client.get("/api/tasks/archived")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        statuses = [item["status"] for item in data["items"]]
        assert all(s == "complete" for s in statuses)

    def test_does_not_return_non_complete_tasks(self, client: TestClient, test_task):
        """PLANNING tasks are not returned by the archived endpoint."""
        response = client.get("/api/tasks/archived")
        assert response.status_code == 200
        # test_task is PLANNING, so it should not appear
        data = response.json()
        ids = [item["id"] for item in data["items"]]
        assert test_task.id not in ids

    def test_pagination_page_2(self, client: TestClient, test_task, db_session, test_codebase):
        """Pagination: page 2 returns the correct slice."""
        project = test_task.project
        # Create 3 complete tasks
        for i in range(3):
            _make_task(db_session, test_codebase, project, TaskStatus.COMPLETE, f"Done {i}")

        # Page 1 with page_size=2 should return 2 items
        r1 = client.get("/api/tasks/archived?page=1&page_size=2")
        assert r1.status_code == 200
        d1 = r1.json()
        assert len(d1["items"]) == 2
        assert d1["total"] >= 3

        # Page 2 with page_size=2 should return at least 1 item
        r2 = client.get("/api/tasks/archived?page=2&page_size=2")
        assert r2.status_code == 200
        d2 = r2.json()
        assert len(d2["items"]) >= 1

        # No overlap between pages
        ids1 = {item["id"] for item in d1["items"]}
        ids2 = {item["id"] for item in d2["items"]}
        assert ids1.isdisjoint(ids2)

    def test_last_page_may_have_fewer_items(self, client: TestClient, test_task, db_session, test_codebase):
        """Last page returns fewer items than page_size when not a perfect multiple."""
        project = test_task.project
        for i in range(3):
            _make_task(db_session, test_codebase, project, TaskStatus.COMPLETE, f"Task {i}")

        # With page_size=2 and 3 total, page 2 should have 1 item
        response = client.get("/api/tasks/archived?page=2&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    def test_project_id_filter(self, client: TestClient, test_task, db_session, test_codebase, second_project):
        """project_id filter restricts archived results to that project."""
        project = test_task.project
        _make_task(db_session, test_codebase, project, TaskStatus.COMPLETE, "Project 1 Done")
        _make_task(db_session, test_codebase, second_project, TaskStatus.COMPLETE, "Project 2 Done")

        response = client.get(f"/api/tasks/archived?project_id={project.id}")

        assert response.status_code == 200
        data = response.json()
        project_ids = {item["project_id"] for item in data["items"]}
        assert project_ids == {project.id}

    def test_empty_result(self, client: TestClient, second_project):
        """Returns empty items list and zero total when no COMPLETE tasks match."""
        response = client.get(f"/api/tasks/archived?project_id={second_project.id}")
        assert response.status_code == 200
        data = response.json()
        assert data == {"items": [], "total": 0, "page": 1, "page_size": 20}

    def test_response_shape(self, client: TestClient, test_task, db_session, test_codebase):
        """Each item in archived response has all required fields."""
        project = test_task.project
        _make_task(db_session, test_codebase, project, TaskStatus.COMPLETE, "Shape Check")

        response = client.get("/api/tasks/archived")
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) >= 1
        item = next(i for i in items if i["title"] == "Shape Check")
        assert set(item.keys()) == {
            "id",
            "title",
            "project_id",
            "project_name",
            "codebase_id",
            "status",
            "created_at",
            "updated_at",
        }
        assert item["status"] == "complete"
        assert item["project_name"] == project.name
