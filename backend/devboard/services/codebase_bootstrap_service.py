"""Service for bootstrapping new codebases with git initialization and starter files."""

from dataclasses import dataclass
from pathlib import Path

import logfire

from devboard.integrations.git import GitRepoIntegration


@dataclass
class DirectoryValidationResult:
    """Result of directory validation for bootstrap."""

    exists: bool
    is_directory: bool
    has_git: bool
    has_commits: bool
    has_remote: bool
    remote_url: str | None
    current_branch: str | None
    needs_bootstrap: bool
    detected_project_type: str | None


@dataclass
class BootstrapRequest:
    """Request to bootstrap a codebase."""

    path: str
    name: str
    description: str
    create_gitignore: bool = True
    create_readme: bool = True
    create_claude_md: bool = True
    branch_name: str = "main"
    initial_commit_message: str = "Initial commit"
    remote_url: str | None = None
    push_to_remote: bool = False


@dataclass
class BootstrapResult:
    """Result of bootstrap operation."""

    success: bool
    commit_hash: str | None
    files_created: list[str]
    error_message: str | None = None


@dataclass
class FilePreview:
    """Preview of a file to be created."""

    path: str
    content: str
    file_type: str  # 'gitignore', 'readme', 'claude_md'


class CodebaseBootstrapService:
    """Service for bootstrapping new codebases."""

    def __init__(self):
        self.template_dir = Path(__file__).parent.parent / "templates" / "bootstrap"

    async def validate_directory(self, path: str) -> DirectoryValidationResult:
        """Validate a directory and determine if bootstrap is needed.

        Args:
            path: Path to the directory

        Returns:
            DirectoryValidationResult with validation details
        """
        dir_path = Path(path).resolve()

        # Check if path exists
        if not dir_path.exists():
            return DirectoryValidationResult(
                exists=False,
                is_directory=False,
                has_git=False,
                has_commits=False,
                has_remote=False,
                remote_url=None,
                current_branch=None,
                needs_bootstrap=True,
                detected_project_type=None,
            )

        # Check if it's a directory
        if not dir_path.is_dir():
            return DirectoryValidationResult(
                exists=True,
                is_directory=False,
                has_git=False,
                has_commits=False,
                has_remote=False,
                remote_url=None,
                current_branch=None,
                needs_bootstrap=False,
                detected_project_type=None,
            )

        # Check for git repository
        git_dir = dir_path / ".git"
        has_git = git_dir.exists()

        # Detect project type
        detected_project_type = self._detect_project_type(dir_path)

        if not has_git:
            return DirectoryValidationResult(
                exists=True,
                is_directory=True,
                has_git=False,
                has_commits=False,
                has_remote=False,
                remote_url=None,
                current_branch=None,
                needs_bootstrap=True,
                detected_project_type=detected_project_type,
            )

        # Check git repository details
        git = GitRepoIntegration(path)
        has_commits = await git.has_commits()
        remote_url = await git.detect_git_remote_url()
        has_remote = remote_url is not None

        current_branch = None
        if has_commits:
            try:
                current_branch = await git.get_current_branch()
            except Exception:
                pass

        # Needs bootstrap if no commits
        needs_bootstrap = not has_commits

        return DirectoryValidationResult(
            exists=True,
            is_directory=True,
            has_git=True,
            has_commits=has_commits,
            has_remote=has_remote,
            remote_url=remote_url,
            current_branch=current_branch,
            needs_bootstrap=needs_bootstrap,
            detected_project_type=detected_project_type,
        )

    def _detect_project_type(self, path: Path) -> str | None:
        """Detect the project type based on files present.

        Args:
            path: Path to the directory

        Returns:
            Project type string or None if unknown
        """
        # Check for Python project markers
        python_markers = ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"]
        for marker in python_markers:
            if (path / marker).exists():
                return "python"

        # Check for Node.js/JavaScript project markers
        node_markers = ["package.json", "yarn.lock", "pnpm-lock.yaml"]
        for marker in node_markers:
            if (path / marker).exists():
                return "node"

        # Check for Rust
        if (path / "Cargo.toml").exists():
            return "rust"

        # Check for Go
        if (path / "go.mod").exists():
            return "go"

        # Check for Ruby
        if (path / "Gemfile").exists():
            return "ruby"

        return None

    def _load_template(self, template_name: str) -> str:
        """Load a template file.

        Args:
            template_name: Name of the template file

        Returns:
            Template content

        Raises:
            FileNotFoundError: If template doesn't exist
        """
        template_path = self.template_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_name}")
        return template_path.read_text(encoding="utf-8")

    def generate_gitignore(self, project_type: str | None) -> str:
        """Generate .gitignore content based on project type.

        Args:
            project_type: Detected project type (python, node, etc.)

        Returns:
            Gitignore content
        """
        if project_type == "python":
            return self._load_template("gitignore_python.template")
        elif project_type == "node":
            return self._load_template("gitignore_node.template")
        else:
            return self._load_template("gitignore_general.template")

    def generate_readme(self, name: str, description: str) -> str:
        """Generate README.md content.

        Args:
            name: Project name
            description: Project description

        Returns:
            README content
        """
        template = self._load_template("readme.md.template")
        return template.replace("{{ name }}", name).replace("{{ description }}", description)

    def generate_claude_md(self, name: str, description: str) -> str:
        """Generate CLAUDE.md content.

        Args:
            name: Project name
            description: Project description

        Returns:
            CLAUDE.md content
        """
        template = self._load_template("claude_md.md.template")
        return template.replace("{{ name }}", name).replace("{{ description }}", description)

    async def preview_bootstrap(
        self,
        path: str,
        name: str,
        description: str,
        create_gitignore: bool = True,
        create_readme: bool = True,
        create_claude_md: bool = True,
    ) -> list[FilePreview]:
        """Preview files that will be created during bootstrap.

        Args:
            path: Path to the directory
            name: Project name
            description: Project description
            create_gitignore: Whether to create .gitignore
            create_readme: Whether to create README.md
            create_claude_md: Whether to create CLAUDE.md

        Returns:
            List of FilePreview objects
        """
        dir_path = Path(path).resolve()
        project_type = self._detect_project_type(dir_path) if dir_path.exists() else None

        previews = []

        if create_gitignore:
            gitignore_path = dir_path / ".gitignore"
            if not gitignore_path.exists():
                previews.append(
                    FilePreview(
                        path=".gitignore",
                        content=self.generate_gitignore(project_type),
                        file_type="gitignore",
                    )
                )

        if create_readme:
            readme_path = dir_path / "README.md"
            if not readme_path.exists():
                previews.append(
                    FilePreview(
                        path="README.md",
                        content=self.generate_readme(name, description),
                        file_type="readme",
                    )
                )

        if create_claude_md:
            claude_path = dir_path / "CLAUDE.md"
            if not claude_path.exists():
                previews.append(
                    FilePreview(
                        path="CLAUDE.md",
                        content=self.generate_claude_md(name, description),
                        file_type="claude_md",
                    )
                )

        return previews

    async def execute_bootstrap(self, request: BootstrapRequest) -> BootstrapResult:
        """Execute the bootstrap process.

        Args:
            request: Bootstrap request with all options

        Returns:
            BootstrapResult with operation outcome
        """
        dir_path = Path(request.path).resolve()
        files_created: list[str] = []

        try:
            # Ensure directory exists
            if not dir_path.exists():
                dir_path.mkdir(parents=True)
                logfire.info(f"Created directory: {dir_path}")

            git = GitRepoIntegration(str(dir_path))

            # Initialize git if needed
            git_dir = dir_path / ".git"
            if not git_dir.exists():
                # Initialize git first
                await git.init_repository()
                logfire.info(f"Initialized git repository at {dir_path}")

            # Detect project type for gitignore
            project_type = self._detect_project_type(dir_path)

            # Create files
            if request.create_gitignore:
                gitignore_path = dir_path / ".gitignore"
                if not gitignore_path.exists():
                    content = self.generate_gitignore(project_type)
                    gitignore_path.write_text(content, encoding="utf-8")
                    files_created.append(".gitignore")
                    logfire.info("Created .gitignore")

            if request.create_readme:
                readme_path = dir_path / "README.md"
                if not readme_path.exists():
                    content = self.generate_readme(request.name, request.description)
                    readme_path.write_text(content, encoding="utf-8")
                    files_created.append("README.md")
                    logfire.info("Created README.md")

            if request.create_claude_md:
                claude_path = dir_path / "CLAUDE.md"
                if not claude_path.exists():
                    content = self.generate_claude_md(request.name, request.description)
                    claude_path.write_text(content, encoding="utf-8")
                    files_created.append("CLAUDE.md")
                    logfire.info("Created CLAUDE.md")

            # Add remote if provided
            if request.remote_url:
                remotes = await git.get_remotes()
                origin_exists = any(r["name"] == "origin" for r in remotes)
                if not origin_exists:
                    await git.add_remote("origin", request.remote_url)
                    logfire.info(f"Added remote origin: {request.remote_url}")

            # Create initial commit
            commit_hash = None
            has_commits = await git.has_commits()
            if not has_commits:
                # Check if there are files to commit (including existing files)
                await git.stage_all()
                # Create commit
                commit_hash = await git.commit(request.initial_commit_message)
                logfire.info(f"Created initial commit: {commit_hash}")

                # Rename branch if needed (in case git config wasn't set before init)
                current_branch = await git.get_current_branch()
                if current_branch != request.branch_name:
                    await git.rename_branch(current_branch, request.branch_name)
                    logfire.info(f"Renamed branch from {current_branch} to {request.branch_name}")

            # Push to remote if requested
            if request.push_to_remote and request.remote_url:
                try:
                    await git.push_with_upstream(request.branch_name)
                    logfire.info(f"Pushed to remote origin/{request.branch_name}")
                except Exception as e:
                    logfire.warning(f"Failed to push to remote: {e}")
                    # Don't fail the whole operation if push fails

            return BootstrapResult(
                success=True,
                commit_hash=commit_hash,
                files_created=files_created,
            )

        except Exception as e:
            logfire.error(f"Bootstrap failed: {e}")
            return BootstrapResult(
                success=False,
                commit_hash=None,
                files_created=files_created,
                error_message=str(e),
            )
