"""Unit tests for BackgroundAgentRun model."""

import datetime

import pytest
from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.background_agent_run import BackgroundAgentRun, BackgroundAgentRunStatus
from devboard.db.repositories import ConversationRepository


@pytest.fixture
def agent(db_session: Session) -> BackgroundAgent:
    a = BackgroundAgent(name="Test Agent", prompt="prompt", engine=AgentEngine.INTERNAL)
    db_session.add(a)
    db_session.flush()
    return a


@pytest.fixture
def conversation(db_session: Session, test_task) -> object:
    repo = ConversationRepository(db_session)
    conv = repo.create(
        parent_entity_type=ParentEntityType.TASK,
        parent_entity_id=test_task.id,
        agent_role=AgentRoleType.TASK_PLANNING,
        engine=AgentEngine.INTERNAL,
        model_id=None,
    )
    db_session.flush()
    return conv


class TestBackgroundAgentRun:
    """Tests for the BackgroundAgentRun model."""

    def test_create_agent_run(self, db_session: Session, agent: BackgroundAgent, conversation) -> None:
        run = BackgroundAgentRun(
            agent_id=agent.id,
            conversation_id=conversation.id,
            triggered_by="manual",
            status=BackgroundAgentRunStatus.COMPLETED,
            state_before={},
            state_after={"result": "done"},
        )
        db_session.add(run)
        db_session.flush()

        assert run.id is not None
        assert run.triggered_by == "manual"
        assert run.status == BackgroundAgentRunStatus.COMPLETED
        assert run.state_before == {}
        assert run.state_after == {"result": "done"}
        assert run.trigger_event_id is None
        assert run.completed_at is None
        assert run.input_tokens is None
        assert run.output_tokens is None
        assert run.error is None

    def test_agent_run_relationships(self, db_session: Session, agent: BackgroundAgent, conversation) -> None:
        run = BackgroundAgentRun(
            agent_id=agent.id,
            conversation_id=conversation.id,
            triggered_by="event:42",
            trigger_event_id="42",
            status=BackgroundAgentRunStatus.FAILED,
            state_before={"counter": 0},
            error="Something went wrong",
        )
        db_session.add(run)
        db_session.flush()
        db_session.refresh(run)

        assert run.agent.id == agent.id
        assert run.conversation.id == conversation.id

    def test_agent_run_with_tokens(self, db_session: Session, agent: BackgroundAgent, conversation) -> None:
        now = datetime.datetime.now(datetime.UTC)
        run = BackgroundAgentRun(
            agent_id=agent.id,
            conversation_id=conversation.id,
            triggered_by="schedule",
            status=BackgroundAgentRunStatus.COMPLETED,
            state_before={},
            state_after={},
            started_at=now,
            completed_at=now,
            input_tokens=100,
            output_tokens=200,
        )
        db_session.add(run)
        db_session.flush()

        assert run.input_tokens == 100
        assert run.output_tokens == 200
        assert run.completed_at is not None

    def test_cascade_delete_agent_runs(self, db_session: Session, agent: BackgroundAgent, conversation) -> None:
        run = BackgroundAgentRun(
            agent_id=agent.id,
            conversation_id=conversation.id,
            triggered_by="manual",
            status=BackgroundAgentRunStatus.CANCELLED,
            state_before={},
        )
        db_session.add(run)
        db_session.flush()
        run_id = run.id

        db_session.delete(agent)
        db_session.flush()

        assert db_session.get(BackgroundAgentRun, run_id) is None
