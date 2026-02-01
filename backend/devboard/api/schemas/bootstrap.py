"""Bootstrap-related Pydantic schemas."""

from pydantic import BaseModel, Field


class ValidatePathRequest(BaseModel):
    """Request to validate a path for codebase bootstrap."""

    path: str = Field(..., description="Path to the directory to validate")


class ValidatePathResponse(BaseModel):
    """Response from path validation."""

    exists: bool = Field(..., description="Whether the path exists")
    is_directory: bool = Field(..., description="Whether the path is a directory")
    has_git: bool = Field(..., description="Whether the path has a .git directory")
    has_commits: bool = Field(..., description="Whether the git repo has any commits")
    has_remote: bool = Field(..., description="Whether a git remote is configured")
    remote_url: str | None = Field(None, description="The remote URL if configured")
    current_branch: str | None = Field(None, description="The current branch name")
    needs_bootstrap: bool = Field(..., description="Whether the directory needs bootstrap")
    detected_project_type: str | None = Field(None, description="Detected project type (python, node, etc.)")


class FilePreviewResponse(BaseModel):
    """Preview of a file to be created."""

    path: str = Field(..., description="Relative path of the file")
    content: str = Field(..., description="Content of the file")
    file_type: str = Field(..., description="Type of file (gitignore, readme, claude_md)")


class BootstrapPreviewRequest(BaseModel):
    """Request to preview bootstrap files."""

    path: str = Field(..., description="Path to the directory")
    name: str = Field(..., description="Project name")
    description: str = Field("", description="Project description")
    create_gitignore: bool = Field(True, description="Whether to create .gitignore")
    create_readme: bool = Field(True, description="Whether to create README.md")
    create_claude_md: bool = Field(True, description="Whether to create CLAUDE.md")


class BootstrapPreviewResponse(BaseModel):
    """Response with file previews."""

    files: list[FilePreviewResponse] = Field(..., description="List of files to be created")


class BootstrapCodebaseRequest(BaseModel):
    """Request to bootstrap a codebase."""

    path: str = Field(..., description="Path to the directory")
    name: str = Field(..., description="Project name")
    description: str = Field("", description="Project description")
    create_gitignore: bool = Field(True, description="Whether to create .gitignore")
    create_readme: bool = Field(True, description="Whether to create README.md")
    create_claude_md: bool = Field(True, description="Whether to create CLAUDE.md")
    branch_name: str = Field("main", description="Name for the default branch")
    initial_commit_message: str = Field("Initial commit", description="Message for the initial commit")
    remote_url: str | None = Field(None, description="Optional remote URL to configure")
    push_to_remote: bool = Field(False, description="Whether to push to remote after commit")


class BootstrapCodebaseResponse(BaseModel):
    """Response from bootstrap operation."""

    success: bool = Field(..., description="Whether bootstrap succeeded")
    commit_hash: str | None = Field(None, description="Hash of the initial commit")
    files_created: list[str] = Field(..., description="List of files created")
    error_message: str | None = Field(None, description="Error message if failed")
