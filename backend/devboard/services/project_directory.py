"""Utility for managing project working directories."""

import os
import re
from pathlib import Path

from devboard.db.models.project import Project


def slugify_project_name(name: str) -> str:
    """Convert project name to a filesystem-safe slug.

    Lowercase, replace non-alphanumeric with hyphens, collapse multiples,
    strip leading/trailing hyphens.
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"


def get_project_directory(project: Project) -> Path:
    """Get the dedicated directory path for a project."""
    devboard_home = Path(os.environ.get("DEVBOARD_HOME", str(Path.home() / ".devboard")))
    return devboard_home / "projects" / slugify_project_name(project.name)


def ensure_project_directory(project: Project) -> Path:
    """Create the project directory if it doesn't exist and return the path."""
    directory = get_project_directory(project)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
