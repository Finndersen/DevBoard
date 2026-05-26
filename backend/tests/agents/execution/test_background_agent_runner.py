"""Tests for BackgroundAgentRunner service."""

from unittest.mock import Mock, patch

import pytest

from devboard.agents.engines import AgentEngine
from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.background_agent_runner import BackgroundAgentRunner, _assemble_initial_message
from devboard.agents.roles import AgentRoleType
from devboard.db.models.background_agent_run import BackgroundAgentRunStatus
from devboard.db.models.enums import EntityType


def _make_agent(
    agent_id: int = 1,
    name: str = "Test Agent",
    engine: AgentEngine = AgentEngine.CLAUDE_CODE,
    model_id: str | None = None,
    state: dict | None = None,
    project_id: int | None = None,
) -> Mock:
    agent = Mock()
    agent.id = agent_id
    agent.name = name
    agent.engine = engine
    agent.model_id = model_id
    agent.state = state or {}
    agent.project_id = project_id
    return agent


def _make_conversation(conversation_id: int = 10) -> Mock:
    conv = Mock()
    conv.id = conversation_id
    return conv


def _make_run(run_id: int = 5) -> Mock:
    run = Mock()
    run.id = run_id
    return run


def _make_log_entry(
    type: str = "task.completed",
    content: str = "A task was completed",
    source: str = "system",
    entry_metadata: dict | None = None,
) -> Mock:
    import datetime

    entry = Mock()
    entry.type = type
    entry.content = content
    entry.source = source
    entry.timestamp = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)
    entry.entry_metadata = entry_metadata
    return entry


class TestAssembleInitialMessage:
    def test_minimal_trigger_omits_optional_sections(self):
        result = _assemble_initial_message(
            triggered_by="manual",
            state={},
            input_message=None,
            trigger_event=None,
        )
        assert "Trigger type: manual" in result
        assert "Current state:" in result
        assert "Triggering event:" not in result
        assert "Input message:" not in result

    def test_includes_input_message_when_provided(self):
        result = _assemble_initial_message(
            triggered_by="manual",
            state={},
            input_message="Please check the logs",
            trigger_event=None,
        )
        assert "Input message:" in result
        assert "Please check the logs" in result

    def test_includes_log_entry_fields_when_trigger_event_provided(self):
        trigger_event = _make_log_entry(type="task.completed", content="done")
        result = _assemble_initial_message(
            triggered_by="event",
            state={},
            input_message=None,
            trigger_event=trigger_event,
        )
        assert "Triggering event:" in result
        assert '"type": "task.completed"' in result
        assert '"content": "done"' in result

    def test_all_fields_combined(self):
        trigger_event = _make_log_entry(type="alert", content="An alert occurred")
        result = _assemble_initial_message(
            triggered_by="schedule",
            state={"last_run": "2024-01-01", "counter": 5},
            input_message="Extra context",
            trigger_event=trigger_event,
        )
        assert result.startswith("Trigger type: schedule")
        assert "Triggering event:" in result
        assert "Input message:" in result
        assert "Extra context" in result
        assert "Current state:" in result
        assert '"last_run": "2024-01-01"' in result


class TestBackgroundAgentRunner:
    @pytest.fixture
    def conversation_repo(self):
        return Mock()

    @pytest.fixture
    def agent_run_repo(self):
        return Mock()

    @pytest.fixture
    def runner(self, conversation_repo, agent_run_repo):
        return BackgroundAgentRunner(
            conversation_repo=conversation_repo,
            agent_run_repo=agent_run_repo,
        )

    @pytest.fixture
    def mock_execution_manager(self):
        return Mock()

    def _patch_execution_manager(self, mock_manager):
        return patch(
            "devboard.agents.execution.background_agent_runner.get_execution_manager",
            return_value=mock_manager,
        )

    def test_creates_conversation_with_correct_fields(
        self, runner, conversation_repo, agent_run_repo, mock_execution_manager
    ):
        agent = _make_agent(agent_id=7, engine=AgentEngine.CLAUDE_CODE, model_id="claude-sonnet-4")
        conversation_repo.create.return_value = _make_conversation(conversation_id=20)
        agent_run_repo.create.return_value = _make_run(run_id=3)

        with self._patch_execution_manager(mock_execution_manager):
            runner.trigger(agent=agent, triggered_by="manual")

        conversation_repo.create.assert_called_once_with(
            parent_entity_type=EntityType.BACKGROUND_AGENT,
            parent_entity_id=7,
            agent_role=AgentRoleType.BACKGROUND_AGENT,
            engine=AgentEngine.CLAUDE_CODE,
            model_id="claude-sonnet-4",
        )

    def test_creates_run_with_correct_fields(self, runner, conversation_repo, agent_run_repo, mock_execution_manager):
        agent = _make_agent(agent_id=7, state={"key": "val"})
        conversation_repo.create.return_value = _make_conversation(conversation_id=20)
        agent_run_repo.create.return_value = _make_run(run_id=3)

        trigger_event = _make_log_entry()
        trigger_event.id = 42

        with self._patch_execution_manager(mock_execution_manager):
            runner.trigger(agent=agent, triggered_by="manual", trigger_event=trigger_event)

        agent_run_repo.create.assert_called_once_with(
            agent_id=7,
            conversation_id=20,
            triggered_by="manual",
            status=BackgroundAgentRunStatus.RUNNING,
            state_before={"key": "val"},
            trigger_event_id=42,
        )

    def test_returns_background_agent_run(self, runner, conversation_repo, agent_run_repo, mock_execution_manager):
        agent = _make_agent()
        conversation_repo.create.return_value = _make_conversation(conversation_id=20)
        mock_run = _make_run(run_id=3)
        mock_run.conversation_id = 20
        agent_run_repo.create.return_value = mock_run

        with self._patch_execution_manager(mock_execution_manager):
            run = runner.trigger(agent=agent, triggered_by="manual")

        assert run.id == 3
        assert run.conversation_id == 20

    def test_calls_start_agent_execution_with_assembled_message(
        self, runner, conversation_repo, agent_run_repo, mock_execution_manager
    ):
        agent = _make_agent(state={"processed": 10})
        conversation_repo.create.return_value = _make_conversation(conversation_id=20)
        agent_run_repo.create.return_value = _make_run(run_id=3)

        with self._patch_execution_manager(mock_execution_manager):
            runner.trigger(agent=agent, triggered_by="schedule", input_message="Check the queue")

        mock_execution_manager.start_agent_execution.assert_called_once()
        call_args = mock_execution_manager.start_agent_execution.call_args
        assert call_args[0][0] == 20  # conversation_id
        initial_message = call_args[0][1]
        assert "Trigger type: schedule" in initial_message
        assert "Check the queue" in initial_message
        assert '"processed": 10' in initial_message

    def test_trigger_event_id_optional(self, runner, conversation_repo, agent_run_repo, mock_execution_manager):
        agent = _make_agent()
        conversation_repo.create.return_value = _make_conversation(conversation_id=20)
        agent_run_repo.create.return_value = _make_run(run_id=3)

        with self._patch_execution_manager(mock_execution_manager):
            runner.trigger(agent=agent, triggered_by="manual")

        agent_run_repo.create.assert_called_once_with(
            agent_id=agent.id,
            conversation_id=20,
            triggered_by="manual",
            status=BackgroundAgentRunStatus.RUNNING,
            state_before=agent.state,
            trigger_event_id=None,
        )

    def test_conversation_busy_error_marks_run_failed_and_reraises(
        self, runner, conversation_repo, agent_run_repo, mock_execution_manager
    ):
        agent = _make_agent()
        conversation_repo.create.return_value = _make_conversation(conversation_id=20)
        mock_run = _make_run(run_id=3)
        agent_run_repo.create.return_value = mock_run
        mock_execution_manager.start_agent_execution.side_effect = ConversationBusyError(20)

        with self._patch_execution_manager(mock_execution_manager):
            with pytest.raises(ConversationBusyError):
                runner.trigger(agent=agent, triggered_by="manual")

        assert mock_run.status == BackgroundAgentRunStatus.FAILED
        assert mock_run.error is not None
