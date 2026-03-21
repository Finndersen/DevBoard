"""Utility for managing project working directories."""

import os
import re
from pathlib import Path

from devboard.db.models.project import Project

_DEFAULT_DEVBOARD_HOME = Path.home() / ".devboard"


def get_devboard_home() -> Path:
    return Path(os.environ.get("DEVBOARD_HOME", str(_DEFAULT_DEVBOARD_HOME)))


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
    return get_devboard_home() / "projects" / slugify_project_name(project.name)


def ensure_project_directory(project: Project) -> Path:
    """Create the project directory if it doesn't exist and return the path."""
    directory = get_project_directory(project)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
