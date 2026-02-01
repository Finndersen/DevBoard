"""Tests for the CodebaseBootstrapService."""

import tempfile
from pathlib import Path

import pytest

from devboard.services.codebase_bootstrap_service import (
    BootstrapRequest,
    CodebaseBootstrapService,
)


@pytest.fixture
def bootstrap_service():
    """Bootstrap service instance for testing."""
    return CodebaseBootstrapService()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_python_dir(temp_dir):
    """Create a temporary directory with Python project marker."""
    pyproject = Path(temp_dir) / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'test-project'\n")
    return temp_dir


@pytest.fixture
def temp_node_dir(temp_dir):
    """Create a temporary directory with Node.js project marker."""
    package_json = Path(temp_dir) / "package.json"
    package_json.write_text('{"name": "test-project"}\n')
    return temp_dir


class TestCodebaseBootstrapService:
    """Test the CodebaseBootstrapService functionality."""

    @pytest.mark.asyncio
    async def test_validate_directory_nonexistent(self, bootstrap_service):
        """Test validating a nonexistent directory."""
        result = await bootstrap_service.validate_directory("/nonexistent/path")

        assert result.exists is False
        assert result.is_directory is False
        assert result.has_git is False
        assert result.has_commits is False
        assert result.needs_bootstrap is True

    @pytest.mark.asyncio
    async def test_validate_directory_exists_no_git(self, bootstrap_service, temp_dir):
        """Test validating a directory without git."""
        result = await bootstrap_service.validate_directory(temp_dir)

        assert result.exists is True
        assert result.is_directory is True
        assert result.has_git is False
        assert result.has_commits is False
        assert result.needs_bootstrap is True

    @pytest.mark.asyncio
    async def test_validate_directory_is_file(self, bootstrap_service, temp_dir):
        """Test validating a path that is a file, not a directory."""
        file_path = Path(temp_dir) / "test_file.txt"
        file_path.write_text("test content")

        result = await bootstrap_service.validate_directory(str(file_path))

        assert result.exists is True
        assert result.is_directory is False
        assert result.needs_bootstrap is False  # Can't bootstrap a file

    @pytest.mark.asyncio
    async def test_detect_python_project(self, bootstrap_service, temp_python_dir):
        """Test that Python project is detected."""
        result = await bootstrap_service.validate_directory(temp_python_dir)

        assert result.detected_project_type == "python"

    @pytest.mark.asyncio
    async def test_detect_node_project(self, bootstrap_service, temp_node_dir):
        """Test that Node.js project is detected."""
        result = await bootstrap_service.validate_directory(temp_node_dir)

        assert result.detected_project_type == "node"

    @pytest.mark.asyncio
    async def test_detect_no_project_type(self, bootstrap_service, temp_dir):
        """Test that unknown project type returns None."""
        result = await bootstrap_service.validate_directory(temp_dir)

        assert result.detected_project_type is None


class TestGitignoreGeneration:
    """Test gitignore file generation."""

    def test_generate_gitignore_python(self, bootstrap_service):
        """Test generating Python gitignore."""
        content = bootstrap_service.generate_gitignore("python")

        assert "__pycache__/" in content
        assert "*.py[cod]" in content
        assert ".venv" in content
        assert ".env" in content

    def test_generate_gitignore_node(self, bootstrap_service):
        """Test generating Node.js gitignore."""
        content = bootstrap_service.generate_gitignore("node")

        assert "node_modules/" in content
        assert "*.log" in content
        assert ".env" in content

    def test_generate_gitignore_general(self, bootstrap_service):
        """Test generating general gitignore."""
        content = bootstrap_service.generate_gitignore(None)

        assert ".env" in content
        assert ".DS_Store" in content
        assert ".idea/" in content


class TestReadmeGeneration:
    """Test README file generation."""

    def test_generate_readme(self, bootstrap_service):
        """Test generating README.md content."""
        content = bootstrap_service.generate_readme("My Project", "A test project description")

        assert "# My Project" in content
        assert "A test project description" in content
        assert "## Getting Started" in content

    def test_generate_readme_empty_description(self, bootstrap_service):
        """Test generating README.md with empty description."""
        content = bootstrap_service.generate_readme("My Project", "")

        assert "# My Project" in content


class TestClaudeMdGeneration:
    """Test CLAUDE.md file generation."""

    def test_generate_claude_md(self, bootstrap_service):
        """Test generating CLAUDE.md content."""
        content = bootstrap_service.generate_claude_md("My Project", "A test project description")

        assert "# My Project" in content
        assert "A test project description" in content
        assert "## Project Structure" in content
        assert "## Development Guidelines" in content


class TestBootstrapPreview:
    """Test bootstrap file preview."""

    @pytest.mark.asyncio
    async def test_preview_all_files(self, bootstrap_service, temp_dir):
        """Test previewing all files to be created."""
        previews = await bootstrap_service.preview_bootstrap(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=True,
        )

        assert len(previews) == 3
        paths = [p.path for p in previews]
        assert ".gitignore" in paths
        assert "README.md" in paths
        assert "CLAUDE.md" in paths

    @pytest.mark.asyncio
    async def test_preview_no_files(self, bootstrap_service, temp_dir):
        """Test previewing with all file options disabled."""
        previews = await bootstrap_service.preview_bootstrap(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=False,
            create_readme=False,
            create_claude_md=False,
        )

        assert len(previews) == 0

    @pytest.mark.asyncio
    async def test_preview_skips_existing_files(self, bootstrap_service, temp_dir):
        """Test that preview skips files that already exist."""
        # Create existing README
        readme_path = Path(temp_dir) / "README.md"
        readme_path.write_text("# Existing README\n")

        previews = await bootstrap_service.preview_bootstrap(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=True,
        )

        paths = [p.path for p in previews]
        assert "README.md" not in paths
        assert ".gitignore" in paths
        assert "CLAUDE.md" in paths


class TestBootstrapExecution:
    """Test bootstrap execution."""

    @pytest.mark.asyncio
    async def test_execute_bootstrap_creates_directory(self, bootstrap_service, temp_dir):
        """Test that bootstrap creates the directory if it doesn't exist."""
        new_dir = Path(temp_dir) / "new_project"

        request = BootstrapRequest(
            path=str(new_dir),
            name="New Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=True,
        )

        result = await bootstrap_service.execute_bootstrap(request)

        assert result.success is True
        assert new_dir.exists()

    @pytest.mark.asyncio
    async def test_execute_bootstrap_creates_files(self, bootstrap_service, temp_dir):
        """Test that bootstrap creates the expected files."""
        request = BootstrapRequest(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=True,
        )

        result = await bootstrap_service.execute_bootstrap(request)

        assert result.success is True
        assert (Path(temp_dir) / ".gitignore").exists()
        assert (Path(temp_dir) / "README.md").exists()
        assert (Path(temp_dir) / "CLAUDE.md").exists()
        assert ".gitignore" in result.files_created
        assert "README.md" in result.files_created
        assert "CLAUDE.md" in result.files_created

    @pytest.mark.asyncio
    async def test_execute_bootstrap_initializes_git(self, bootstrap_service, temp_dir):
        """Test that bootstrap initializes git."""
        request = BootstrapRequest(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=False,
        )

        result = await bootstrap_service.execute_bootstrap(request)

        assert result.success is True
        assert (Path(temp_dir) / ".git").exists()
        assert result.commit_hash is not None

    @pytest.mark.asyncio
    async def test_execute_bootstrap_sets_branch_name(self, bootstrap_service, temp_dir):
        """Test that bootstrap sets the correct branch name."""
        request = BootstrapRequest(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=False,
            branch_name="develop",
        )

        result = await bootstrap_service.execute_bootstrap(request)

        assert result.success is True

        # Check the branch name
        from devboard.integrations.git import GitRepoIntegration

        git = GitRepoIntegration(temp_dir)
        current_branch = await git.get_current_branch()
        assert current_branch == "develop"

    @pytest.mark.asyncio
    async def test_execute_bootstrap_does_not_overwrite_existing_files(self, bootstrap_service, temp_dir):
        """Test that bootstrap does not overwrite existing files."""
        # Create existing README
        readme_path = Path(temp_dir) / "README.md"
        original_content = "# Existing README\n"
        readme_path.write_text(original_content)

        request = BootstrapRequest(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=True,
        )

        result = await bootstrap_service.execute_bootstrap(request)

        assert result.success is True
        assert "README.md" not in result.files_created
        assert readme_path.read_text() == original_content

    @pytest.mark.asyncio
    async def test_execute_bootstrap_adds_remote(self, bootstrap_service, temp_dir):
        """Test that bootstrap adds a remote if URL is provided."""
        request = BootstrapRequest(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=False,
            remote_url="https://github.com/user/repo.git",
            push_to_remote=False,  # Don't actually push
        )

        result = await bootstrap_service.execute_bootstrap(request)

        assert result.success is True

        # Check the remote was added
        from devboard.integrations.git import GitRepoIntegration

        git = GitRepoIntegration(temp_dir)
        remotes = await git.get_remotes()
        assert len(remotes) == 1
        assert remotes[0]["name"] == "origin"
        assert remotes[0]["url"] == "https://github.com/user/repo.git"

    @pytest.mark.asyncio
    async def test_execute_bootstrap_custom_commit_message(self, bootstrap_service, temp_dir):
        """Test that bootstrap uses custom commit message."""
        request = BootstrapRequest(
            path=temp_dir,
            name="Test Project",
            description="Test description",
            create_gitignore=True,
            create_readme=True,
            create_claude_md=False,
            initial_commit_message="Custom initial commit message",
        )

        result = await bootstrap_service.execute_bootstrap(request)

        assert result.success is True

        # Check the commit message
        from devboard.integrations.git import GitRepoIntegration

        git = GitRepoIntegration(temp_dir)
        logs = await git.get_git_log(max_count=1)
        assert len(logs) == 1
        assert logs[0].message == "Custom initial commit message"
