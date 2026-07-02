"""Tests for project hierarchy (initiatives) router endpoints and task list integration."""

from unittest.mock import patch

import pytest

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.document import DocumentType
from devboard.db.models.task import TaskStatus
from devboard.db.repositories import (
    ConversationRepository,
    DocumentRepository,
    ProjectRepository,
    TaskRepository,
)


def _create_project(db_session, name="Test Project", description="desc", parent_project_id=None):
    """Helper to create a project with a specification document."""
    doc_repo = DocumentRepository(db_session)
    project_repo = ProjectRepository(db_session)
    spec_doc = doc_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(
        name=name,
        description=description,
        specification=spec_doc,
        parent_project_id=parent_project_id,
    )
    db_session.commit()
    return project


def _create_task(db_session, project_id, codebase_id, title="Test Task"):
    """Helper to create a task with a spec doc and conversation."""
    doc_repo = DocumentRepository(db_session)
    task_repo = TaskRepository(db_session)
    conv_repo = ConversationRepository(db_session)

    spec_doc = doc_repo.create(DocumentType.TASK_SPECIFICATION, "")
    task = task_repo.create(
        project_id=project_id,
        title=title,
        specification=spec_doc,
        base_branch="main",
        branch_name=f"task-{title.lower().replace(' ', '-')}",
        codebase_id=codebase_id,
        status=TaskStatus.PLANNING,
    )
    conv_repo.create(
        parent_entity_type=ParentEntityType.TASK,
        parent_entity_id=task.id,
        agent_role=AgentRoleType.TASK_PLANNING,
        engine=AgentEngine.INTERNAL,
        model_id="openai:gpt-4",
    )
    db_session.commit()
    return task


class TestProjectHierarchyRouter:
    """Tests for project hierarchy (initiative) creation and listing."""

    @pytest.fixture(autouse=True)
    def mock_project_directory(self):
        with patch("devboard.services.project_service.ensure_project_directory"):
            yield

    def test_create_initiative_succeeds(self, client, db_session):
        """Creating a project with a valid parent_project_id creates an initiative."""
        parent = _create_project(db_session, name="Parent Project")

        response = client.post(
            "/api/projects/",
            json={"name": "My Initiative", "description": "sub-project", "parent_project_id": parent.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Initiative"
        assert data["parent_project_id"] == parent.id
        assert data["parent_project_name"] == "Parent Project"
        assert data["complete"] is False

    def test_create_sub_sub_project_rejected(self, client, db_session):
        """Reject creating an initiative under another initiative (>1 level nesting)."""
        parent = _create_project(db_session, name="Top Level")
        initiative = _create_project(db_session, name="Initiative", parent_project_id=parent.id)

        response = client.post(
            "/api/projects/",
            json={"name": "Sub-sub", "description": "too deep", "parent_project_id": initiative.id},
        )
        assert response.status_code == 400
        assert "one level" in response.json()["detail"].lower()

    def test_create_project_with_nonexistent_parent_rejected(self, client, db_session):
        """Reject creating an initiative with a non-existent parent ID."""
        response = client.post(
            "/api/projects/",
            json={"name": "Orphan", "description": "bad parent", "parent_project_id": 99999},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_list_projects_excludes_complete_by_default(self, client, db_session):
        """Default project list excludes complete projects."""
        _create_project(db_session, name="Active Project")
        complete = _create_project(db_session, name="Done Project")

        project_repo = ProjectRepository(db_session)
        done = project_repo.get_by_id(complete.id)
        done.complete = True
        db_session.commit()

        response = client.get("/api/projects/")
        assert response.status_code == 200
        names = [p["name"] for p in response.json()]
        assert "Active Project" in names
        assert "Done Project" not in names

    def test_list_projects_complete_filter(self, client, db_session):
        """Passing complete=true returns only complete projects."""
        _create_project(db_session, name="Active")
        complete = _create_project(db_session, name="Archived")

        project_repo = ProjectRepository(db_session)
        done = project_repo.get_by_id(complete.id)
        done.complete = True
        db_session.commit()

        response = client.get("/api/projects/?complete=true")
        assert response.status_code == 200
        names = [p["name"] for p in response.json()]
        assert "Archived" in names
        assert "Active" not in names

    def test_list_projects_filtered_by_parent_project_id(self, client, db_session):
        """Filtering by parent_project_id returns only that project's initiatives."""
        parent_a = _create_project(db_session, name="Parent A")
        parent_b = _create_project(db_session, name="Parent B")
        _create_project(db_session, name="Initiative A1", parent_project_id=parent_a.id)
        _create_project(db_session, name="Initiative A2", parent_project_id=parent_a.id)
        _create_project(db_session, name="Initiative B1", parent_project_id=parent_b.id)

        response = client.get(f"/api/projects/?parent_project_id={parent_a.id}")
        assert response.status_code == 200
        names = [p["name"] for p in response.json()]
        assert "Initiative A1" in names
        assert "Initiative A2" in names
        assert "Initiative B1" not in names
        assert "Parent A" not in names

    def test_get_project_includes_parent_info(self, client, db_session):
        """GET /projects/{id} returns parent_project_id and parent_project_name for initiatives."""
        parent = _create_project(db_session, name="Epic Project")
        initiative = _create_project(db_session, name="Story Initiative", parent_project_id=parent.id)

        conv_repo = ConversationRepository(db_session)
        conv_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=initiative.id,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
            is_active=True,
        )
        db_session.commit()

        response = client.get(f"/api/projects/{initiative.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["parent_project_id"] == parent.id
        assert data["parent_project_name"] == "Epic Project"

    def test_update_project_complete_flag(self, client, db_session):
        """PATCH can toggle the complete flag on a project."""
        project = _create_project(db_session, name="To Complete")

        response = client.patch(f"/api/projects/{project.id}", json={"complete": True})
        assert response.status_code == 200
        assert response.json()["complete"] is True

        # Toggle back
        response = client.patch(f"/api/projects/{project.id}", json={"complete": False})
        assert response.status_code == 200
        assert response.json()["complete"] is False

    def test_update_project_parent_project_id(self, client, db_session):
        """PATCH can set parent_project_id to make a project an initiative."""
        parent = _create_project(db_session, name="New Parent")
        child = _create_project(db_session, name="To Nest")

        response = client.patch(f"/api/projects/{child.id}", json={"parent_project_id": parent.id})
        assert response.status_code == 200
        data = response.json()
        assert data["parent_project_id"] == parent.id
        assert data["parent_project_name"] == "New Parent"

    def test_update_project_self_referential_parent_rejected(self, client, db_session):
        """PATCH rejects setting parent_project_id to the project's own ID."""
        project = _create_project(db_session, name="Self Parent")

        response = client.patch(f"/api/projects/{project.id}", json={"parent_project_id": project.id})
        assert response.status_code == 400
        assert "own parent" in response.json()["detail"].lower()

    def test_update_project_nested_parent_rejected(self, client, db_session):
        """PATCH rejects setting parent_project_id to an initiative (would create >1 level nesting)."""
        top = _create_project(db_session, name="Top")
        middle = _create_project(db_session, name="Middle", parent_project_id=top.id)
        bottom = _create_project(db_session, name="Bottom")

        response = client.patch(f"/api/projects/{bottom.id}", json={"parent_project_id": middle.id})
        assert response.status_code == 400
        assert "one level" in response.json()["detail"].lower()


class TestTaskListWithInitiatives:
    """Tests for task list endpoint with initiative hierarchy data."""

    def test_task_list_includes_initiative_fields_for_initiative_tasks(self, client, db_session, test_codebase):
        """Tasks under an initiative have initiative_id/initiative_name populated."""
        parent = _create_project(db_session, name="Top Project")
        initiative = _create_project(db_session, name="My Initiative", parent_project_id=parent.id)
        _create_task(db_session, project_id=initiative.id, codebase_id=test_codebase.id, title="Initiative Task")

        response = client.get("/api/tasks/")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        task = tasks[0]
        assert task["initiative_id"] == initiative.id
        assert task["initiative_name"] == "My Initiative"
        assert task["project_name"] == "Top Project"
        assert task["project_id"] == initiative.id

    def test_task_list_no_initiative_fields_for_direct_project_tasks(self, client, db_session, test_codebase):
        """Tasks under a top-level project have no initiative fields."""
        project = _create_project(db_session, name="Direct Project")
        _create_task(db_session, project_id=project.id, codebase_id=test_codebase.id, title="Direct Task")

        response = client.get("/api/tasks/")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        task = tasks[0]
        assert task["initiative_id"] is None
        assert task["initiative_name"] is None
        assert task["project_name"] == "Direct Project"

    def test_task_list_filter_by_top_level_project_includes_initiative_tasks(self, client, db_session, test_codebase):
        """Filtering tasks by a top-level project_id also returns tasks from its initiatives."""
        parent = _create_project(db_session, name="Epic")
        initiative = _create_project(db_session, name="Story", parent_project_id=parent.id)
        other_project = _create_project(db_session, name="Other")

        _create_task(db_session, project_id=parent.id, codebase_id=test_codebase.id, title="Direct Task")
        _create_task(db_session, project_id=initiative.id, codebase_id=test_codebase.id, title="Initiative Task")
        _create_task(db_session, project_id=other_project.id, codebase_id=test_codebase.id, title="Other Task")

        response = client.get(f"/api/tasks/?project_id={parent.id}")
        assert response.status_code == 200
        titles = [t["title"] for t in response.json()]
        assert "Direct Task" in titles
        assert "Initiative Task" in titles
        assert "Other Task" not in titles

    def test_task_list_filter_by_initiative_returns_only_that_initiatives_tasks(
        self, client, db_session, test_codebase
    ):
        """Filtering tasks by an initiative project_id returns only that initiative's tasks."""
        parent = _create_project(db_session, name="Epic")
        initiative_a = _create_project(db_session, name="Story A", parent_project_id=parent.id)
        initiative_b = _create_project(db_session, name="Story B", parent_project_id=parent.id)

        _create_task(db_session, project_id=initiative_a.id, codebase_id=test_codebase.id, title="Task A")
        _create_task(db_session, project_id=initiative_b.id, codebase_id=test_codebase.id, title="Task B")

        response = client.get(f"/api/tasks/?project_id={initiative_a.id}")
        assert response.status_code == 200
        titles = [t["title"] for t in response.json()]
        assert "Task A" in titles
        assert "Task B" not in titles
