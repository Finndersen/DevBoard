"""Tests for project hierarchy in ProjectRepository."""

import pytest
from sqlalchemy.orm import Session

from devboard.db.models.document import DocumentType
from devboard.db.repositories import DocumentRepository, ProjectRepository


class TestProjectHierarchyRepository:
    """Tests for ProjectRepository hierarchy and completion filtering."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ProjectRepository:
        return ProjectRepository(db_session)

    def _make_project(self, repo: ProjectRepository, db_session, name="Project", parent_project_id=None):
        doc_repo = DocumentRepository(db_session)
        spec = doc_repo.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = repo.create(name=name, description="", specification=spec, parent_project_id=parent_project_id)
        db_session.commit()
        return project

    def test_create_initiative_sets_parent_project_id(self, repo, db_session):
        """Creating a project with parent_project_id stores it correctly."""
        parent = self._make_project(repo, db_session, name="Parent")
        initiative = self._make_project(repo, db_session, name="Initiative", parent_project_id=parent.id)

        assert initiative.parent_project_id == parent.id

    def test_get_by_id_eager_loads_parent(self, repo, db_session):
        """get_by_id eagerly loads the parent relationship."""
        parent = self._make_project(repo, db_session, name="Parent")
        initiative = self._make_project(repo, db_session, name="Initiative", parent_project_id=parent.id)

        retrieved = repo.get_by_id(initiative.id)
        assert retrieved is not None
        assert retrieved.parent is not None
        assert retrieved.parent.name == "Parent"
        assert retrieved.parent_project_name == "Parent"

    def test_get_by_id_parent_is_none_for_top_level(self, repo, db_session):
        """get_by_id returns parent=None for top-level projects."""
        project = self._make_project(repo, db_session, name="Top Level")
        retrieved = repo.get_by_id(project.id)
        assert retrieved is not None
        assert retrieved.parent is None
        assert retrieved.parent_project_name is None

    def test_get_all_excludes_complete_by_default(self, repo, db_session):
        """get_all() returns only non-complete projects by default."""
        self._make_project(repo, db_session, name="Active")
        done = self._make_project(repo, db_session, name="Done")
        done.complete = True
        db_session.commit()

        results = repo.get_all()
        names = [p.name for p in results]
        assert "Active" in names
        assert "Done" not in names

    def test_get_all_complete_true_returns_only_complete(self, repo, db_session):
        """get_all(complete=True) returns only complete projects."""
        self._make_project(repo, db_session, name="Active")
        done = self._make_project(repo, db_session, name="Done")
        done.complete = True
        db_session.commit()

        results = repo.get_all(complete=True)
        names = [p.name for p in results]
        assert "Done" in names
        assert "Active" not in names

    def test_get_all_filtered_by_parent_project_id(self, repo, db_session):
        """get_all(parent_project_id=X) returns only initiatives under X."""
        parent_a = self._make_project(repo, db_session, name="Parent A")
        parent_b = self._make_project(repo, db_session, name="Parent B")
        self._make_project(repo, db_session, name="Initiative A1", parent_project_id=parent_a.id)
        self._make_project(repo, db_session, name="Initiative A2", parent_project_id=parent_a.id)
        self._make_project(repo, db_session, name="Initiative B1", parent_project_id=parent_b.id)

        results = repo.get_all(parent_project_id=parent_a.id)
        names = [p.name for p in results]
        assert "Initiative A1" in names
        assert "Initiative A2" in names
        assert "Initiative B1" not in names
        assert "Parent A" not in names

    def test_get_all_parent_project_id_filter_with_complete_default(self, repo, db_session):
        """get_all with parent_project_id still excludes complete initiatives by default."""
        parent = self._make_project(repo, db_session, name="Parent")
        self._make_project(repo, db_session, name="Active Initiative", parent_project_id=parent.id)
        done_init = self._make_project(repo, db_session, name="Done Initiative", parent_project_id=parent.id)
        done_init.complete = True
        db_session.commit()

        results = repo.get_all(parent_project_id=parent.id)
        names = [p.name for p in results]
        assert "Active Initiative" in names
        assert "Done Initiative" not in names

    def test_complete_defaults_to_false_on_creation(self, repo, db_session):
        """Newly created projects have complete=False."""
        project = self._make_project(repo, db_session, name="New Project")
        assert project.complete is False
