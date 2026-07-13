"""Tests for initiative router endpoints and task list integration."""

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
    InitiativeRepository,
    ProjectRepository,
    TaskRepository,
)


def _create_project(db_session, name="Test Project", description="desc"):
    """Helper to create a project with a specification document."""
    doc_repo = DocumentRepository(db_session)
    project_repo = ProjectRepository(db_session)
    spec_doc = doc_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
    project = project_repo.create(
        name=name,
        description=description,
        specification=spec_doc,
    )
    db_session.commit()
    return project


def _create_initiative(db_session, project_id, name="Test Initiative", description="initiative desc"):
    """Helper to create an initiative under a project."""
    doc_repo = DocumentRepository(db_session)
    initiative_repo = InitiativeRepository(db_session)
    spec_doc = doc_repo.create(DocumentType.INITIATIVE_CONTEXT, "")
    initiative = initiative_repo.create(
        name=name,
        description=description,
        specification=spec_doc,
        project_id=project_id,
    )
    db_session.commit()
    return initiative


def _create_task(db_session, project_id, codebase_id, title="Test Task", initiative_id=None):
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
    if initiative_id is not None:
        task.initiative_id = initiative_id
        db_session.flush()

    conv_repo.create(
        parent_entity_type=ParentEntityType.TASK,
        parent_entity_id=task.id,
        agent_role=AgentRoleType.TASK_PLANNING,
        engine=AgentEngine.INTERNAL,
        model_id="openai:gpt-4",
    )
    db_session.commit()
    return task


class TestInitiativeEndpoints:
    """Tests for initiative CRUD endpoints under /api/projects/{id}/initiatives."""

    @pytest.fixture(autouse=True)
    def mock_project_directory(self):
        with patch("devboard.services.project_service.ensure_project_directory"):
            yield

    def test_create_initiative_succeeds(self, client, db_session):
        """Creating an initiative under a valid project returns 201 with initiative data."""
        project = _create_project(db_session, name="Parent Project")

        response = client.post(
            f"/api/projects/{project.id}/initiatives",
            json={"name": "My Initiative", "description": "some scope"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Initiative"
        assert data["description"] == "some scope"
        assert data["project_id"] == project.id
        assert data["complete"] is False
        assert "specification_document_id" in data
        assert "id" in data

    def test_create_initiative_under_nonexistent_project_returns_404(self, client, db_session):
        """Creating an initiative under a non-existent project returns 404."""
        response = client.get("/api/projects/99999/initiatives")
        assert response.status_code == 404

    def test_list_initiatives_for_project(self, client, db_session):
        """Listing initiatives returns all non-complete initiatives by default."""
        project = _create_project(db_session, name="Epic")
        _create_initiative(db_session, project.id, name="Initiative A")
        _create_initiative(db_session, project.id, name="Initiative B")

        response = client.get(f"/api/projects/{project.id}/initiatives")
        assert response.status_code == 200
        names = [i["name"] for i in response.json()]
        assert "Initiative A" in names
        assert "Initiative B" in names

    def test_list_initiatives_excludes_complete_by_default(self, client, db_session):
        """Default initiative list excludes completed initiatives."""
        project = _create_project(db_session, name="Epic")
        _create_initiative(db_session, project.id, name="Active")
        done = _create_initiative(db_session, project.id, name="Done")

        initiative_repo = InitiativeRepository(db_session)
        done_initiative = initiative_repo.get_by_id(done.id)
        done_initiative.complete = True
        db_session.commit()

        response = client.get(f"/api/projects/{project.id}/initiatives")
        assert response.status_code == 200
        names = [i["name"] for i in response.json()]
        assert "Active" in names
        assert "Done" not in names

    def test_list_initiatives_complete_filter(self, client, db_session):
        """Passing complete=true returns only completed initiatives."""
        project = _create_project(db_session, name="Epic")
        _create_initiative(db_session, project.id, name="Active")
        done = _create_initiative(db_session, project.id, name="Done")

        initiative_repo = InitiativeRepository(db_session)
        done_initiative = initiative_repo.get_by_id(done.id)
        done_initiative.complete = True
        db_session.commit()

        response = client.get(f"/api/projects/{project.id}/initiatives?complete=true")
        assert response.status_code == 200
        names = [i["name"] for i in response.json()]
        assert "Done" in names
        assert "Active" not in names

    def test_get_initiative_returns_details(self, client, db_session):
        """GET /projects/{id}/initiatives/{initiative_id} returns the initiative."""
        project = _create_project(db_session, name="Epic")
        initiative = _create_initiative(db_session, project.id, name="Story")

        response = client.get(f"/api/projects/{project.id}/initiatives/{initiative.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == initiative.id
        assert data["name"] == "Story"
        assert data["project_id"] == project.id

    def test_get_initiative_from_different_project_returns_404(self, client, db_session):
        """Accessing an initiative with mismatched project_id returns 404."""
        project_a = _create_project(db_session, name="Project A")
        project_b = _create_project(db_session, name="Project B")
        initiative = _create_initiative(db_session, project_a.id, name="A's Initiative")

        response = client.get(f"/api/projects/{project_b.id}/initiatives/{initiative.id}")
        assert response.status_code == 404


class TestProjectsWithoutHierarchy:
    """Tests verifying that project endpoints no longer support hierarchy fields."""

    @pytest.fixture(autouse=True)
    def mock_project_directory(self):
        with patch("devboard.services.project_service.ensure_project_directory"):
            yield

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

    def test_project_response_has_no_parent_fields(self, client, db_session):
        """Project responses do not include parent_project_id or parent_project_name."""
        project = _create_project(db_session, name="Standalone")

        conv_repo = ConversationRepository(db_session)
        conv_repo.create(
            parent_entity_type=ParentEntityType.PROJECT,
            parent_entity_id=project.id,
            agent_role=AgentRoleType.PROJECT,
            engine=AgentEngine.INTERNAL,
            model_id="openai:gpt-4",
            is_active=True,
        )
        db_session.commit()

        response = client.get(f"/api/projects/{project.id}")
        assert response.status_code == 200
        data = response.json()
        assert "parent_project_id" not in data
        assert "parent_project_name" not in data

    def test_update_project_complete_flag(self, client, db_session):
        """PATCH can toggle the complete flag on a project."""
        project = _create_project(db_session, name="To Complete")

        response = client.patch(f"/api/projects/{project.id}", json={"complete": True})
        assert response.status_code == 200
        assert response.json()["complete"] is True

        response = client.patch(f"/api/projects/{project.id}", json={"complete": False})
        assert response.status_code == 200
        assert response.json()["complete"] is False


class TestTaskListWithInitiatives:
    """Tests for task list endpoint with initiative data from the Initiative model."""

    def test_task_list_includes_initiative_fields_for_initiative_tasks(self, client, db_session, test_codebase):
        """Tasks linked to an initiative have initiative_id/initiative_name populated."""
        project = _create_project(db_session, name="Top Project")
        initiative = _create_initiative(db_session, project.id, name="My Initiative")
        _create_task(
            db_session,
            project_id=project.id,
            codebase_id=test_codebase.id,
            title="Initiative Task",
            initiative_id=initiative.id,
        )

        response = client.get("/api/tasks/")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) == 1
        task = tasks[0]
        assert task["initiative_id"] == initiative.id
        assert task["initiative_name"] == "My Initiative"
        assert task["project_name"] == "Top Project"
        assert task["project_id"] == project.id

    def test_task_list_no_initiative_fields_for_direct_project_tasks(self, client, db_session, test_codebase):
        """Tasks not linked to an initiative have null initiative fields."""
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

    def test_task_list_filter_by_project_id_includes_initiative_tasks(self, client, db_session, test_codebase):
        """Filtering tasks by project_id returns both direct and initiative tasks."""
        project = _create_project(db_session, name="Epic")
        initiative = _create_initiative(db_session, project.id, name="Story")
        other_project = _create_project(db_session, name="Other")

        _create_task(db_session, project_id=project.id, codebase_id=test_codebase.id, title="Direct Task")
        _create_task(
            db_session,
            project_id=project.id,
            codebase_id=test_codebase.id,
            title="Initiative Task",
            initiative_id=initiative.id,
        )
        _create_task(db_session, project_id=other_project.id, codebase_id=test_codebase.id, title="Other Task")

        response = client.get(f"/api/tasks/?project_id={project.id}")
        assert response.status_code == 200
        titles = [t["title"] for t in response.json()]
        assert "Direct Task" in titles
        assert "Initiative Task" in titles
        assert "Other Task" not in titles
