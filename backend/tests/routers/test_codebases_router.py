"""Tests for codebases router."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.db.models import Codebase
from devboard.db.repositories import CodebaseRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_git_repo():
    """Mock GitRepoIntegration for a valid git repo with a remote."""
    with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.detect_git_remote_url = AsyncMock(return_value="https://github.com/test/repo.git")
        mock_instance.has_commits = AsyncMock(return_value=True)
        mock_instance.get_default_branch = AsyncMock(return_value="main")
        yield mock_cls


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
        """Test creating a new codebase from a non-git directory fails."""
        response = client.post("/api/codebases/", json=test_codebase_data)
        assert response.status_code == 400
        assert "no commits" in response.json()["detail"]

    def test_create_codebase_with_git(self, client, temp_dir, mock_git_repo):
        """Test creating a new codebase from a git directory."""
        codebase_data = {
            "name": "Git Test Codebase",
            "local_path": temp_dir,
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

    def test_create_codebase_creates_main_repo_slot(self, client, db_session, temp_dir, mock_git_repo):
        """Test that creating a codebase also creates a main repo worktree slot."""
        codebase_data = {
            "name": "Git Test Codebase",
            "local_path": temp_dir,
            "description": "A test codebase with git repository",
        }

        response = client.post("/api/codebases/", json=codebase_data)
        assert response.status_code == 200

        result = response.json()
        codebase_id = result["id"]

        # Verify main repo slot was created
        worktree_slot_repo = WorktreeSlotRepository(db_session)
        slots = worktree_slot_repo.get_by_codebase(codebase_id, include_main=True)

        assert len(slots) == 1
        main_slot = slots[0]
        assert main_slot.is_main_repo is True
        assert main_slot.path == temp_dir
        assert main_slot.codebase_id == codebase_id

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

    def test_create_codebase_tilde_path_expanded(self, client):
        """Tilde in local_path is expanded; a nonexistent ~ path returns a path-not-found 400."""
        data = {
            "name": "TildeTest",
            "local_path": "~/devboard_nonexistent_test_xyz",
            "description": "",
        }
        response = client.post("/api/codebases/", json=data)
        assert response.status_code == 400
        assert "Local path does not exist" in response.json()["detail"]


class TestCloneCodebase:
    """Tests for POST /api/codebases/clone."""

    @pytest.fixture
    def mock_clone_git(self):
        """Mock GitRepoIntegration.clone_repo returning a valid git instance."""
        with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
            mock_instance = Mock()
            mock_instance.detect_git_remote_url = AsyncMock(return_value="https://github.com/org/my-repo.git")
            mock_instance.get_default_branch = AsyncMock(return_value="main")
            mock_cls.clone_repo = AsyncMock(return_value=mock_instance)
            yield mock_cls, mock_instance

    def test_clone_codebase_success(self, client, temp_dir, mock_clone_git):
        """Test successful clone registers the codebase with auto-detected values."""
        data = {
            "repository_url": "https://github.com/org/my-repo.git",
            "parent_directory": temp_dir,
        }
        response = client.post("/api/codebases/clone", json=data)
        assert response.status_code == 200
        result = response.json()
        assert result["name"] == "my-repo"
        assert result["repository_url"] == "https://github.com/org/my-repo.git"
        assert result["branch_handling"] == "github_pr"
        assert result["default_branch"] == "main"
        assert "id" in result

    def test_clone_codebase_name_auto_derived_from_url(self, client, temp_dir, mock_clone_git):
        """Name is derived from the last URL segment, stripping .git."""
        mock_cls, _ = mock_clone_git
        data = {
            "repository_url": "https://github.com/org/some-project.git",
            "parent_directory": temp_dir,
        }
        response = client.post("/api/codebases/clone", json=data)
        assert response.status_code == 200
        call_args = mock_cls.clone_repo.call_args[0]
        assert call_args[1].name == "some-project"

    def test_clone_codebase_explicit_name_overrides_url(self, client, temp_dir, mock_clone_git):
        """Explicit name field takes precedence over auto-derived name."""
        data = {
            "repository_url": "https://github.com/org/my-repo.git",
            "parent_directory": temp_dir,
            "name": "custom-name",
        }
        response = client.post("/api/codebases/clone", json=data)
        assert response.status_code == 200
        assert response.json()["name"] == "custom-name"

    def test_clone_codebase_creates_main_repo_slot(self, client, db_session, temp_dir, mock_clone_git):
        """Clone endpoint should bootstrap a main worktree slot."""
        data = {
            "repository_url": "https://github.com/org/my-repo.git",
            "parent_directory": temp_dir,
        }
        response = client.post("/api/codebases/clone", json=data)
        assert response.status_code == 200
        codebase_id = response.json()["id"]

        worktree_slot_repo = WorktreeSlotRepository(db_session)
        slots = worktree_slot_repo.get_by_codebase(codebase_id, include_main=True)
        assert len(slots) == 1
        assert slots[0].is_main_repo is True
        assert slots[0].codebase_id == codebase_id

    def test_clone_codebase_parent_not_exist(self, client):
        """Return 400 when the parent directory does not exist."""
        data = {
            "repository_url": "https://github.com/org/my-repo.git",
            "parent_directory": "/nonexistent/path",
        }
        response = client.post("/api/codebases/clone", json=data)
        assert response.status_code == 400
        assert "Parent directory does not exist" in response.json()["detail"]

    def test_clone_codebase_target_exists(self, client, temp_dir, mock_clone_git):
        """Return 400 when the target directory already exists."""
        target = Path(temp_dir) / "my-repo"
        target.mkdir()

        data = {
            "repository_url": "https://github.com/org/my-repo.git",
            "parent_directory": temp_dir,
        }
        response = client.post("/api/codebases/clone", json=data)
        assert response.status_code == 400
        assert "Target directory already exists" in response.json()["detail"]

    def test_clone_name_derived_from_url_variants(self, client, temp_dir, mock_clone_git):
        """Name auto-derivation handles HTTPS, no-suffix, and SSH-style URLs."""
        mock_cls, _ = mock_clone_git
        for url, expected_name in [
            ("https://github.com/org/my-repo.git", "my-repo"),
            ("https://github.com/org/no-suffix", "no-suffix"),
            ("git@github.com:org/ssh-repo.git", "ssh-repo"),
        ]:
            payload = {"repository_url": url, "parent_directory": temp_dir}
            response = client.post("/api/codebases/clone", json=payload)
            assert response.status_code == 200
            assert response.json()["name"] == expected_name

    def test_clone_git_failure_returns_400(self, client, temp_dir):
        """A git clone failure surfaces as a 400, not a 500."""
        from devboard.integrations.shell import ShellCommandExecutionError

        with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
            mock_cls.clone_repo = AsyncMock(side_effect=ShellCommandExecutionError("clone failed"))

            payload = {
                "repository_url": "https://github.com/org/bad-repo.git",
                "parent_directory": temp_dir,
            }
            response = client.post("/api/codebases/clone", json=payload)
            assert response.status_code == 400
            assert "Git clone failed" in response.json()["detail"]

    def test_clone_git_failure_cleans_up_directory(self, client, temp_dir):
        """Orphaned directory is removed when clone fails after partial creation."""
        from devboard.integrations.shell import ShellCommandExecutionError

        target = Path(temp_dir) / "bad-repo"

        async def clone_and_create(url, path):
            Path(path).mkdir(parents=True, exist_ok=True)
            raise ShellCommandExecutionError("clone failed")

        with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
            mock_cls.clone_repo = AsyncMock(side_effect=clone_and_create)
            payload = {
                "repository_url": "https://github.com/org/bad-repo.git",
                "parent_directory": temp_dir,
            }
            client.post("/api/codebases/clone", json=payload)

        assert not target.exists()

    def test_clone_tilde_parent_directory_expanded(self, client):
        """Tilde in parent_directory is expanded; a nonexistent ~ path returns a 400."""
        data = {
            "repository_url": "https://github.com/org/my-repo.git",
            "parent_directory": "~/devboard_nonexistent_test_xyz",
        }
        response = client.post("/api/codebases/clone", json=data)
        assert response.status_code == 400
        assert "Parent directory does not exist" in response.json()["detail"]


class TestInitCodebase:
    """Tests for POST /api/codebases/init."""

    @pytest.fixture
    def mock_init_git(self):
        """Mock GitRepoIntegration.init_repo; creates the directory as the real impl would."""
        with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
            mock_instance = Mock()
            mock_instance.detect_git_remote_url = AsyncMock(return_value=None)
            mock_instance.get_default_branch = AsyncMock(return_value="main")
            mock_instance.add_and_commit = AsyncMock(return_value=None)
            mock_instance.write_initial_project_files = Mock(return_value=None)

            async def fake_init_repo(path: Path) -> Mock:
                path.mkdir(parents=True, exist_ok=True)
                return mock_instance

            mock_cls.init_repo = fake_init_repo
            yield mock_cls, mock_instance

    def test_init_codebase_success(self, client, temp_dir, mock_init_git):
        """Test successful init creates codebase with direct_merge branch handling."""
        _, mock_instance = mock_init_git
        data = {
            "name": "MyProject",
            "directory": str(Path(temp_dir) / "MyProject"),
            "description": "A new project",
        }
        response = client.post("/api/codebases/init", json=data)
        assert response.status_code == 200
        result = response.json()
        assert result["name"] == "MyProject"
        assert result["description"] == "A new project"
        assert result["branch_handling"] == "direct_merge"
        assert result["repository_url"] is None
        assert "id" in result
        mock_instance.add_and_commit.assert_called_once_with("Initial commit")

    def test_init_codebase_calls_write_initial_project_files(self, client, temp_dir, mock_init_git):
        """Init endpoint delegates file creation to write_initial_project_files."""
        _, mock_instance = mock_init_git
        data = {
            "name": "MyProject",
            "directory": str(Path(temp_dir) / "MyProject"),
            "description": "My description",
        }
        response = client.post("/api/codebases/init", json=data)
        assert response.status_code == 200
        mock_instance.write_initial_project_files.assert_called_once_with("MyProject", "My description")

    def test_init_codebase_write_initial_project_files_no_description(self, client, temp_dir, mock_init_git):
        """write_initial_project_files is called with None when no description is given."""
        _, mock_instance = mock_init_git
        data = {
            "name": "MyProject",
            "directory": str(Path(temp_dir) / "MyProject"),
        }
        response = client.post("/api/codebases/init", json=data)
        assert response.status_code == 200
        mock_instance.write_initial_project_files.assert_called_once_with("MyProject", None)

    def test_init_codebase_creates_main_repo_slot(self, client, db_session, temp_dir, mock_init_git):
        """Init endpoint should bootstrap a main worktree slot."""
        data = {
            "name": "MyProject",
            "directory": str(Path(temp_dir) / "MyProject"),
        }
        response = client.post("/api/codebases/init", json=data)
        assert response.status_code == 200
        codebase_id = response.json()["id"]

        worktree_slot_repo = WorktreeSlotRepository(db_session)
        slots = worktree_slot_repo.get_by_codebase(codebase_id, include_main=True)
        assert len(slots) == 1
        assert slots[0].is_main_repo is True
        assert slots[0].codebase_id == codebase_id

    def test_init_codebase_target_exists(self, client, temp_dir, mock_init_git):
        """Return 400 when the target directory already exists."""
        target = Path(temp_dir) / "MyProject"
        target.mkdir()

        data = {
            "name": "MyProject",
            "directory": str(target),
        }
        response = client.post("/api/codebases/init", json=data)
        assert response.status_code == 400
        assert "Target directory already exists" in response.json()["detail"]

    def test_init_git_failure_returns_400(self, client, temp_dir):
        """A git failure during init surfaces as a 400, not a 500."""
        from devboard.integrations.shell import ShellCommandExecutionError

        with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
            mock_cls.init_repo = AsyncMock(side_effect=ShellCommandExecutionError("init failed"))
            payload = {"name": "MyProject", "directory": str(Path(temp_dir) / "MyProject")}
            response = client.post("/api/codebases/init", json=payload)
            assert response.status_code == 400
            assert "Git operation failed" in response.json()["detail"]

    def test_init_git_failure_cleans_up_directory(self, client, temp_dir):
        """Orphaned directory is removed when git commit fails after init."""
        from devboard.integrations.shell import ShellCommandExecutionError

        target = Path(temp_dir) / "MyProject"

        with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:
            mock_instance = Mock()
            mock_instance.write_initial_project_files = Mock(return_value=None)
            mock_instance.add_and_commit = AsyncMock(side_effect=ShellCommandExecutionError("commit failed"))

            async def fake_init(path):
                Path(path).mkdir(parents=True, exist_ok=True)
                return mock_instance

            mock_cls.init_repo = AsyncMock(side_effect=fake_init)
            payload = {"name": "MyProject", "directory": str(Path(temp_dir) / "MyProject")}
            client.post("/api/codebases/init", json=payload)

        assert not target.exists()

    def test_init_tilde_directory_expanded(self, client):
        """Tilde in directory is expanded to the absolute home directory path before init."""
        from devboard.integrations.shell import ShellCommandExecutionError

        received_paths: list[Path] = []

        with patch("devboard.api.routers.codebases.GitRepoIntegration") as mock_cls:

            async def fake_init(path: Path) -> Mock:
                received_paths.append(path)
                raise ShellCommandExecutionError("captured")

            mock_cls.init_repo = fake_init

            expected = Path.home() / "devboard_tilde_init_test_xyz"
            data = {"name": "TildeProject", "directory": "~/devboard_tilde_init_test_xyz"}
            response = client.post("/api/codebases/init", json=data)
            assert response.status_code == 400
            assert "Git operation failed" in response.json()["detail"]
            assert len(received_paths) == 1
            assert received_paths[0] == expected
