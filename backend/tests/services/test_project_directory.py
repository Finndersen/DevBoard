"""Tests for project directory utility functions."""

from unittest.mock import Mock

from devboard.db.models.project import Project
from devboard.services.project_directory import (
    ensure_project_directory,
    get_project_directory,
    slugify_project_name,
)


class TestSlugifyProjectName:
    """Tests for slugify_project_name function."""

    def test_normal_name(self):
        assert slugify_project_name("My Cool Project") == "my-cool-project"

    def test_multiple_spaces(self):
        assert slugify_project_name("Project   With   Spaces") == "project-with-spaces"

    def test_special_characters(self):
        assert slugify_project_name("Project @#$% Name!") == "project-name"

    def test_leading_trailing_special_chars(self):
        assert slugify_project_name("---Project---") == "project"

    def test_empty_string(self):
        assert slugify_project_name("") == "unnamed"

    def test_only_special_chars(self):
        assert slugify_project_name("@#$%^&*") == "unnamed"

    def test_single_word(self):
        assert slugify_project_name("devboard") == "devboard"

    def test_numbers_preserved(self):
        assert slugify_project_name("Project 2024") == "project-2024"

    def test_mixed_case(self):
        assert slugify_project_name("MyProject") == "myproject"


class TestGetProjectDirectory:
    """Tests for get_project_directory function."""

    def test_returns_correct_path_structure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        project = Mock(spec=Project)
        project.name = "My Project"

        result = get_project_directory(project)

        assert result == tmp_path / "projects" / "my-project"

    def test_uses_default_devboard_home(self, monkeypatch):
        monkeypatch.delenv("DEVBOARD_HOME", raising=False)

        project = Mock(spec=Project)
        project.name = "Test"

        from pathlib import Path

        result = get_project_directory(project)
        expected = Path.home() / ".devboard" / "projects" / "test"
        assert result == expected


class TestEnsureProjectDirectory:
    """Tests for ensure_project_directory function."""

    def test_creates_directory_if_not_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        project = Mock(spec=Project)
        project.name = "New Project"

        result = ensure_project_directory(project)

        expected = tmp_path / "projects" / "new-project"
        assert result == expected
        assert result.is_dir()

    def test_returns_path_if_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        project = Mock(spec=Project)
        project.name = "Existing Project"

        expected = tmp_path / "projects" / "existing-project"
        expected.mkdir(parents=True)

        result = ensure_project_directory(project)

        assert result == expected
        assert result.is_dir()
