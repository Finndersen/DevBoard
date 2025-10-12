"""Tests for repository classes."""

import pytest
from sqlalchemy.orm import Session

from devboard.db.models.document import DocumentType
from devboard.db.repositories import (
    DocumentRepository,
    ProjectRepository,
)


class TestProjectRepository:
    """Tests for ProjectRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> ProjectRepository:
        return ProjectRepository(db_session)

    @pytest.fixture
    def sample_project_data(self, document_repository) -> dict:
        spec_doc = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        return {"name": "Test Project", "description": "A test project", "specification": spec_doc}

    def test_create_project(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test creating a new project."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        assert created.id is not None
        assert created.name == "Test Project"
        assert created.description == "A test project"

    def test_get_by_id(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test getting a project by ID."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repo: ProjectRepository):
        """Test getting a project by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all(self, repo: ProjectRepository, document_repository, db_session):
        """Test getting all projects."""
        spec_doc1 = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        spec_doc2 = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        repo.create(name="Project 1", description="", specification=spec_doc1)
        repo.create(name="Project 2", description="", specification=spec_doc2)
        db_session.commit()

        all_projects = repo.get_all()
        assert len(all_projects) == 2
        project_names = [p.name for p in all_projects]
        assert "Project 1" in project_names
        assert "Project 2" in project_names

    def test_update_project(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test updating a project."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        created.name = "Updated Project"
        created.description = "Updated description"

        updated = repo.update(created)
        db_session.commit()
        assert updated.name == "Updated Project"
        assert updated.description == "Updated description"

    def test_delete_by_id(self, repo: ProjectRepository, sample_project_data: dict, db_session):
        """Test deleting a project by ID."""
        created = repo.create(**sample_project_data)
        db_session.commit()
        result = repo.delete_by_id(created.id)
        db_session.commit()

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: ProjectRepository):
        """Test deleting a project by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False
