"""Tests for event tools functionality."""

import datetime
from unittest.mock import Mock

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.event_tools import create_create_event_tool, create_query_events_tool
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.background_agent_run import BackgroundAgentRun
from devboard.db.models.log_entry import LogEntry, LogEntrySource, LogEntryStatus
from devboard.db.repositories.background_agent import BackgroundAgentRunRepository
from devboard.services.log_entry_service import LogEntryService

UTC = datetime.UTC
FIXED_TS = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)


@pytest.fixture
def mock_background_agent():
    agent = Mock(spec=BackgroundAgent)
    agent.id = 5
    agent.name = "TestAgent"
    agent.project_id = 100
    return agent


@pytest.fixture
def mock_log_entry_service():
    return Mock(spec=LogEntryService)


@pytest.fixture
def mock_agent_run_repo():
    repo = Mock(spec=BackgroundAgentRunRepository)
    run = Mock(spec=BackgroundAgentRun)
    run.id = 99
    repo.get_by_conversation_id.return_value = run
    return repo


@pytest.fixture
def sample_log_entries():
    entries = []
    for i in range(3):
        entry = Mock(spec=LogEntry)
        entry.id = i + 1
        entry.timestamp = FIXED_TS + datetime.timedelta(hours=i)
        entry.type = f"task.event_{i}"
        entry.source = LogEntrySource.AGENT
        entry.status = LogEntryStatus.ACTIVE
        entry.project_id = 100
        entry.task_id = None if i == 0 else 10 + i
        entry.pinned = i == 0
        entry.content = f"Event content {i}" if i < 2 else "A" * 250
        entries.append(entry)
    return entries


class TestQueryEventsTool:
    @pytest.mark.asyncio
    async def test_returns_csv_table_with_auto_injected_project(
        self, mock_log_entry_service, mock_background_agent, sample_log_entries
    ):
        mock_log_entry_service.query_log_entries.return_value = sample_log_entries

        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        result = await tool.function()

        call_kwargs = mock_log_entry_service.query_log_entries.call_args[1]
        assert call_kwargs["project_id"] == 100  # auto-injected
        assert call_kwargs["limit"] == 50  # default

        assert "Found 3 events" in result
        assert "id,timestamp,type,source,status,project_id,task_id,pinned,content" in result
        assert "task.event_0" in result

    @pytest.mark.asyncio
    async def test_explicit_project_id_overrides_auto_inject(
        self, mock_log_entry_service, mock_background_agent, sample_log_entries
    ):
        mock_log_entry_service.query_log_entries.return_value = sample_log_entries
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        await tool.function(project_id=200)
        assert mock_log_entry_service.query_log_entries.call_args[1]["project_id"] == 200

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_log_entry_service, mock_background_agent):
        mock_log_entry_service.query_log_entries.return_value = []
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        result = await tool.function()
        assert "Found 0 events" in result

    @pytest.mark.asyncio
    async def test_invalid_since_raises_model_retry(self, mock_log_entry_service, mock_background_agent):
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        with pytest.raises(ModelRetry, match="Invalid 'since' datetime format"):
            await tool.function(since="not-a-date")

    @pytest.mark.asyncio
    async def test_status_parsed_as_enum(self, mock_log_entry_service, mock_background_agent, sample_log_entries):
        mock_log_entry_service.query_log_entries.return_value = sample_log_entries
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        await tool.function(status="resolved")
        assert mock_log_entry_service.query_log_entries.call_args[1]["status"] == LogEntryStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_invalid_status_raises_model_retry(self, mock_log_entry_service, mock_background_agent):
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        with pytest.raises(ModelRetry, match="Invalid status"):
            await tool.function(status="invalid_status")

    @pytest.mark.asyncio
    async def test_long_content_truncated_in_csv(self, mock_log_entry_service, mock_background_agent):
        entry = Mock(spec=LogEntry)
        entry.id = 1
        entry.timestamp = FIXED_TS
        entry.type = "test.event"
        entry.source = LogEntrySource.AGENT
        entry.status = LogEntryStatus.ACTIVE
        entry.project_id = 100
        entry.task_id = None
        entry.pinned = False
        entry.content = "A" * 300

        mock_log_entry_service.query_log_entries.return_value = [entry]
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        result = await tool.function()

        assert "A" * 200 in result
        assert "A" * 201 not in result
        assert "..." in result

    @pytest.mark.asyncio
    async def test_csv_escapes_quotes_and_newlines(self, mock_log_entry_service, mock_background_agent):
        entry = Mock(spec=LogEntry)
        entry.id = 1
        entry.timestamp = FIXED_TS
        entry.type = "test.event"
        entry.source = LogEntrySource.AGENT
        entry.status = LogEntryStatus.ACTIVE
        entry.project_id = 100
        entry.task_id = None
        entry.pinned = False
        entry.content = 'Test with "quotes" and\nnewlines'

        mock_log_entry_service.query_log_entries.return_value = [entry]
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        result = await tool.function()

        assert '""quotes""' in result
        assert "\\n" in result

    @pytest.mark.asyncio
    async def test_overflow_hint_when_results_equal_limit(
        self, mock_log_entry_service, mock_background_agent, sample_log_entries
    ):
        mock_log_entry_service.query_log_entries.return_value = sample_log_entries
        tool = create_query_events_tool(mock_log_entry_service, mock_background_agent)
        result = await tool.function(limit=3)
        assert "3 results returned (the limit)" in result


class TestCreateEventTool:
    @pytest.fixture
    def created_entry(self):
        entry = Mock(spec=LogEntry)
        entry.id = 42
        return entry

    @pytest.mark.asyncio
    async def test_creates_event_with_correct_fixed_fields(
        self, mock_log_entry_service, mock_background_agent, mock_agent_run_repo, created_entry
    ):
        mock_log_entry_service.create_log_entry.return_value = created_entry
        tool = create_create_event_tool(mock_log_entry_service, mock_background_agent, mock_agent_run_repo, 42)
        result = await tool.function(event_type="task.started", content="Task started")

        assert "Event created successfully with ID 42" in result
        call_kwargs = mock_log_entry_service.create_log_entry.call_args[1]
        assert call_kwargs["source"] == LogEntrySource.AGENT
        assert call_kwargs["status"] == LogEntryStatus.ACTIVE
        assert call_kwargs["project_id"] == 100  # auto-injected
        assert call_kwargs["pinned"] is False

    @pytest.mark.asyncio
    async def test_explicit_project_id_overrides_auto_inject(
        self, mock_log_entry_service, mock_background_agent, mock_agent_run_repo, created_entry
    ):
        mock_log_entry_service.create_log_entry.return_value = created_entry
        tool = create_create_event_tool(mock_log_entry_service, mock_background_agent, mock_agent_run_repo, 42)
        await tool.function(event_type="test.event", content="Test", project_id=200)
        assert mock_log_entry_service.create_log_entry.call_args[1]["project_id"] == 200

    @pytest.mark.asyncio
    async def test_metadata_includes_agent_identity_and_run_id(
        self, mock_log_entry_service, mock_background_agent, mock_agent_run_repo, created_entry
    ):
        mock_log_entry_service.create_log_entry.return_value = created_entry
        tool = create_create_event_tool(mock_log_entry_service, mock_background_agent, mock_agent_run_repo, 42)
        await tool.function(event_type="test.event", content="Test", metadata={"custom_field": "custom_value"})

        metadata = mock_log_entry_service.create_log_entry.call_args[1]["entry_metadata"]
        assert metadata["agent_id"] == 5
        assert metadata["agent_name"] == "TestAgent"
        assert metadata["agent_run_id"] == 99
        assert metadata["custom_field"] == "custom_value"

    @pytest.mark.asyncio
    async def test_pinned_flag_passed_through(
        self, mock_log_entry_service, mock_background_agent, mock_agent_run_repo, created_entry
    ):
        mock_log_entry_service.create_log_entry.return_value = created_entry
        tool = create_create_event_tool(mock_log_entry_service, mock_background_agent, mock_agent_run_repo, 42)
        await tool.function(event_type="test.event", content="Test", pinned=True)
        assert mock_log_entry_service.create_log_entry.call_args[1]["pinned"] is True

    @pytest.mark.asyncio
    async def test_agent_run_id_is_none_when_no_run_found(
        self, mock_log_entry_service, mock_background_agent, created_entry
    ):
        mock_log_entry_service.create_log_entry.return_value = created_entry
        no_run_repo = Mock(spec=BackgroundAgentRunRepository)
        no_run_repo.get_by_conversation_id.return_value = None

        tool = create_create_event_tool(mock_log_entry_service, mock_background_agent, no_run_repo, 99)
        await tool.function(event_type="test.event", content="Test")

        assert mock_log_entry_service.create_log_entry.call_args[1]["entry_metadata"]["agent_run_id"] is None
