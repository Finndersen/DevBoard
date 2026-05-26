"""Tests for background agent directory utility functions."""

from pathlib import Path
from unittest.mock import Mock

from devboard.db.models.background_agent import BackgroundAgent
from devboard.services.background_agent_directory import (
    ensure_background_agent_directory,
    get_background_agent_directory,
)


class TestGetBackgroundAgentDirectory:
    def test_returns_correct_path_structure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        agent = Mock(spec=BackgroundAgent)
        agent.name = "My Agent"

        result = get_background_agent_directory(agent)

        assert result == tmp_path / "background_agents" / "my-agent"

    def test_uses_default_devboard_home(self, monkeypatch):
        monkeypatch.delenv("DEVBOARD_HOME", raising=False)

        agent = Mock(spec=BackgroundAgent)
        agent.name = "Test Agent"

        result = get_background_agent_directory(agent)
        expected = Path.home() / ".devboard" / "background_agents" / "test-agent"
        assert result == expected

    def test_slugifies_special_characters(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        agent = Mock(spec=BackgroundAgent)
        agent.name = "Agent @#$ 2024!"

        result = get_background_agent_directory(agent)

        assert result == tmp_path / "background_agents" / "agent-2024"

    def test_slugifies_mixed_case(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        agent = Mock(spec=BackgroundAgent)
        agent.name = "MonitorAgent"

        result = get_background_agent_directory(agent)

        assert result == tmp_path / "background_agents" / "monitoragent"


class TestEnsureBackgroundAgentDirectory:
    def test_creates_directory_if_not_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        agent = Mock(spec=BackgroundAgent)
        agent.name = "New Agent"

        result = ensure_background_agent_directory(agent)

        expected = tmp_path / "background_agents" / "new-agent"
        assert result == expected
        assert result.is_dir()

    def test_returns_path_if_already_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        agent = Mock(spec=BackgroundAgent)
        agent.name = "Existing Agent"

        expected = tmp_path / "background_agents" / "existing-agent"
        expected.mkdir(parents=True)

        result = ensure_background_agent_directory(agent)

        assert result == expected
        assert result.is_dir()

    def test_creates_nested_directories(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEVBOARD_HOME", str(tmp_path))

        agent = Mock(spec=BackgroundAgent)
        agent.name = "Deep Agent"

        result = ensure_background_agent_directory(agent)

        assert result.is_dir()
        assert (tmp_path / "background_agents").is_dir()
