"""Utility for managing background agent working directories."""

from pathlib import Path

from devboard.db.models.background_agent import BackgroundAgent
from devboard.services.project_directory import get_devboard_home, slugify_project_name


def get_background_agent_directory(agent: BackgroundAgent) -> Path:
    """Get the dedicated directory path for a background agent."""
    return get_devboard_home() / "background_agents" / slugify_project_name(agent.name)


def ensure_background_agent_directory(agent: BackgroundAgent) -> Path:
    """Create the background agent directory if it doesn't exist and return the path."""
    directory = get_background_agent_directory(agent)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
