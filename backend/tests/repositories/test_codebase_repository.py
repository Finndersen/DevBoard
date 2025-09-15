import pytest
from sqlalchemy.orm import Session

from devboard.db.models import Codebase
from devboard.db.repositories import CodebaseRepository


class TestCodebaseRepository:
    """Tests for CodebaseRepository."""

    @pytest.fixture
    def repo(self, db_session: Session) -> CodebaseRepository:
        return CodebaseRepository(db_session)

    @pytest.fixture
    def sample_codebase(self) -> Codebase:
        return Codebase(
            name="Test Codebase",
            description="A test codebase",
            repository_url="https://github.com/test/repo",
            local_path="/path/to/repo",
        )

    def test_create_codebase(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test creating a new codebase."""
        created = repo.create(sample_codebase)
        assert created.id is not None
        assert created.name == "Test Codebase"
        assert created.repository_url == "https://github.com/test/repo"
        assert created.description == "A test codebase"

    def test_get_by_id(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test getting a codebase by ID."""
        created = repo.create(sample_codebase)
        retrieved = repo.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repo: CodebaseRepository):
        """Test getting a codebase by ID when it doesn't exist."""
        result = repo.get_by_id(999)
        assert result is None

    def test_get_all(self, repo: CodebaseRepository):
        """Test getting all codebases."""
        codebase1 = Codebase(
            name="Repo 1",
            description="",
            repository_url="https://github.com/test/repo1",
            local_path="/path/to/repo1",
        )
        codebase2 = Codebase(
            name="Repo 2",
            description="",
            repository_url="https://github.com/test/repo2",
            local_path="/path/to/repo2",
        )

        repo.create(codebase1)
        repo.create(codebase2)

        all_codebases = repo.get_all()
        assert len(all_codebases) == 2
        codebase_names = [c.name for c in all_codebases]
        assert "Repo 1" in codebase_names
        assert "Repo 2" in codebase_names

    def test_update_codebase(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test updating a codebase."""
        created = repo.create(sample_codebase)
        created.name = "Updated Codebase"
        created.description = "Updated description"

        updated = repo.update(created)
        assert updated.name == "Updated Codebase"
        assert updated.description == "Updated description"

    def test_delete_by_id(self, repo: CodebaseRepository, sample_codebase: Codebase):
        """Test deleting a codebase by ID."""
        created = repo.create(sample_codebase)
        result = repo.delete_by_id(created.id)

        assert result is True
        assert repo.get_by_id(created.id) is None

    def test_delete_by_id_not_found(self, repo: CodebaseRepository):
        """Test deleting a codebase by ID when it doesn't exist."""
        result = repo.delete_by_id(999)
        assert result is False
