"""Tests for background agent state and run history tools."""

import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.background_agent_tools import (
    create_query_agent_runs_tool,
    create_read_agent_state_tool,
    create_read_state_tool,
    create_update_state_tool,
)
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.background_agent_run import BackgroundAgentRun, BackgroundAgentRunStatus
from devboard.db.repositories.background_agent import BackgroundAgentRepository, BackgroundAgentRunRepository

pytest_plugins = ("pytest_asyncio",)


# --- Fixtures ---


@pytest.fixture
def mock_background_agent():
    agent = Mock(spec=BackgroundAgent)
    agent.id = 1
    agent.state = {}
    return agent


@pytest.fixture
def mock_background_agent_with_state():
    agent = Mock(spec=BackgroundAgent)
    agent.id = 2
    agent.state = {"counter": 42, "last_run": "2026-05-26T10:00:00Z"}
    return agent


@pytest.fixture
def mock_background_agent_repo():
    return Mock(spec=BackgroundAgentRepository)


@pytest.fixture
def mock_run():
    run = Mock(spec=BackgroundAgentRun)
    run.id = 1
    run.agent_id = 10
    run.status = BackgroundAgentRunStatus.COMPLETED
    run.triggered_by = "manual"
    run.conversation_id = 100
    run.started_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    run.completed_at = datetime(2024, 1, 15, 10, 5, 0, tzinfo=UTC)
    run.input_tokens = 500
    run.output_tokens = 300
    run.error = None
    return run


@pytest.fixture
def mock_failed_run():
    run = Mock(spec=BackgroundAgentRun)
    run.id = 2
    run.agent_id = 10
    run.status = BackgroundAgentRunStatus.FAILED
    run.triggered_by = "event:42"
    run.conversation_id = 101
    run.started_at = datetime(2024, 1, 15, 9, 0, 0, tzinfo=UTC)
    run.completed_at = datetime(2024, 1, 15, 9, 2, 0, tzinfo=UTC)
    run.input_tokens = 400
    run.output_tokens = 100
    run.error = "Agent crashed unexpectedly"
    return run


@pytest.fixture
def mock_run_repo():
    return Mock(spec=BackgroundAgentRunRepository)


@pytest.fixture
def mock_agent_for_runs():
    agent = Mock(spec=BackgroundAgent)
    agent.id = 10
    return agent


# --- State tools ---


class TestReadStateTool:
    @pytest.mark.asyncio
    async def test_returns_empty_state_message_when_empty(self, mock_background_agent):
        tool = create_read_state_tool(mock_background_agent)
        result = await tool.function()
        assert result == "State is empty."

    @pytest.mark.asyncio
    async def test_returns_json_state_when_populated(self, mock_background_agent_with_state):
        tool = create_read_state_tool(mock_background_agent_with_state)
        result = await tool.function()
        assert json.loads(result) == {"counter": 42, "last_run": "2026-05-26T10:00:00Z"}


class TestUpdateStateTool:
    @pytest.mark.asyncio
    async def test_merges_partial_state_and_updates_db(self, mock_background_agent, mock_background_agent_repo):
        mock_background_agent.state = {"counter": 1}
        mock_background_agent_repo.update_state.return_value = Mock(
            spec=BackgroundAgent, id=1, state={"counter": 1, "new_key": "value"}
        )

        tool = create_update_state_tool(mock_background_agent_repo, mock_background_agent)
        result = await tool.function({"new_key": "value"})

        assert "State updated successfully" in result
        assert "new_key" in result
        mock_background_agent_repo.update_state.assert_called_once_with(1, {"new_key": "value"})
        assert mock_background_agent.state == {"counter": 1, "new_key": "value"}

    @pytest.mark.asyncio
    async def test_returns_message_when_no_changes_provided(self, mock_background_agent, mock_background_agent_repo):
        tool = create_update_state_tool(mock_background_agent_repo, mock_background_agent)
        result = await tool.function({})
        assert "No changes provided" in result
        mock_background_agent_repo.update_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_model_retry_when_db_update_fails(self, mock_background_agent, mock_background_agent_repo):
        mock_background_agent_repo.update_state.return_value = None
        tool = create_update_state_tool(mock_background_agent_repo, mock_background_agent)
        with pytest.raises(ModelRetry, match="Failed to update state"):
            await tool.function({"key": "value"})


class TestReadAgentStateTool:
    @pytest.mark.asyncio
    async def test_reads_another_agents_state(self, mock_background_agent_repo, mock_background_agent_with_state):
        mock_background_agent_repo.get_by_id.return_value = mock_background_agent_with_state
        tool = create_read_agent_state_tool(mock_background_agent_repo)
        result = await tool.function(agent_id=2)
        assert json.loads(result) == {"counter": 42, "last_run": "2026-05-26T10:00:00Z"}
        mock_background_agent_repo.get_by_id.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_returns_empty_message_when_state_is_empty(self, mock_background_agent_repo):
        agent = Mock(spec=BackgroundAgent)
        agent.state = {}
        mock_background_agent_repo.get_by_id.return_value = agent
        tool = create_read_agent_state_tool(mock_background_agent_repo)
        result = await tool.function(agent_id=3)
        assert "state is empty" in result.lower()

    @pytest.mark.asyncio
    async def test_raises_model_retry_when_agent_not_found(self, mock_background_agent_repo):
        mock_background_agent_repo.get_by_id.return_value = None
        tool = create_read_agent_state_tool(mock_background_agent_repo)
        with pytest.raises(ModelRetry, match="not found"):
            await tool.function(agent_id=999)


# --- Agent run tools ---


class TestQueryAgentRuns:
    @pytest.mark.asyncio
    async def test_returns_formatted_table_for_agent(self, mock_run, mock_run_repo, mock_agent_for_runs):
        mock_run_repo.get_runs_for_agent.return_value = [mock_run]
        tool = create_query_agent_runs_tool(mock_run_repo, mock_agent_for_runs)
        result = await tool.function(agent_id=10, limit=20)

        mock_run_repo.get_runs_for_agent.assert_called_once_with(10, status=None, limit=20)
        assert "completed" in result.lower()
        assert "manual" in result.lower()
        assert "100" in result  # conversation_id
        assert "2024-01-15" in result

    @pytest.mark.asyncio
    async def test_defaults_agent_id_to_current_agent(self, mock_run, mock_run_repo, mock_agent_for_runs):
        mock_run_repo.get_runs_for_agent.return_value = [mock_run]
        tool = create_query_agent_runs_tool(mock_run_repo, mock_agent_for_runs)
        await tool.function(limit=20)
        mock_run_repo.get_runs_for_agent.assert_called_once_with(10, status=None, limit=20)

    @pytest.mark.asyncio
    async def test_filters_by_status(self, mock_failed_run, mock_run_repo, mock_agent_for_runs):
        mock_run_repo.get_runs_for_agent.return_value = [mock_failed_run]
        tool = create_query_agent_runs_tool(mock_run_repo, mock_agent_for_runs)
        result = await tool.function(agent_id=10, status="failed", limit=20)

        mock_run_repo.get_runs_for_agent.assert_called_once_with(10, status=BackgroundAgentRunStatus.FAILED, limit=20)
        assert "Agent crashed unexpectedly" in result

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_run_repo, mock_agent_for_runs):
        mock_run_repo.get_runs_for_agent.return_value = []
        tool = create_query_agent_runs_tool(mock_run_repo, mock_agent_for_runs)
        result = await tool.function(agent_id=10, limit=20)
        assert "No runs found for agent 10" in result

    @pytest.mark.asyncio
    async def test_invalid_status_raises_model_retry(self, mock_run_repo, mock_agent_for_runs):
        tool = create_query_agent_runs_tool(mock_run_repo, mock_agent_for_runs)
        with pytest.raises(ModelRetry, match="Invalid status.*invalid_status"):
            await tool.function(agent_id=10, status="invalid_status")

    @pytest.mark.asyncio
    async def test_shows_overflow_hint_when_results_equal_limit(
        self, mock_run, mock_failed_run, mock_run_repo, mock_agent_for_runs
    ):
        mock_run_repo.get_runs_for_agent.return_value = [mock_run, mock_failed_run]
        tool = create_query_agent_runs_tool(mock_run_repo, mock_agent_for_runs)
        result = await tool.function(agent_id=10, limit=2)
        assert "2 results returned (the limit)" in result

    @pytest.mark.asyncio
    async def test_handles_null_completed_at(self, mock_run_repo, mock_agent_for_runs):
        running_run = Mock(spec=BackgroundAgentRun)
        running_run.id = 3
        running_run.agent_id = 10
        running_run.status = BackgroundAgentRunStatus.RUNNING
        running_run.triggered_by = "schedule"
        running_run.conversation_id = 102
        running_run.started_at = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        running_run.completed_at = None
        running_run.input_tokens = 200
        running_run.output_tokens = None
        running_run.error = None

        mock_run_repo.get_runs_for_agent.return_value = [running_run]
        tool = create_query_agent_runs_tool(mock_run_repo, mock_agent_for_runs)
        result = await tool.function(agent_id=10, limit=20)

        assert "running" in result.lower()
        assert "null" in result  # TOON encodes None as null
