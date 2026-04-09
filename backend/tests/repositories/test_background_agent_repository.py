"""Tests for BackgroundAgentRepository and BackgroundAgentRunRepository."""

import datetime

import pytest
from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.agents.roles import AgentRoleType
from devboard.db.models import ParentEntityType
from devboard.db.models.background_agent import (
    BackgroundAgent,
    BackgroundAgentEventTrigger,
    BackgroundAgentScheduleTrigger,
)
from devboard.db.models.background_agent_run import BackgroundAgentRun, BackgroundAgentRunStatus
from devboard.db.repositories import BackgroundAgentRepository, BackgroundAgentRunRepository, ConversationRepository

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_repo(db_session: Session) -> BackgroundAgentRepository:
    return BackgroundAgentRepository(db_session)


@pytest.fixture
def run_repo(db_session: Session) -> BackgroundAgentRunRepository:
    return BackgroundAgentRunRepository(db_session)


@pytest.fixture
def agent(db_session: Session, agent_repo: BackgroundAgentRepository) -> BackgroundAgent:
    return agent_repo.create(name="Test Agent", prompt="You are helpful.", engine=AgentEngine.INTERNAL)


@pytest.fixture
def conversation(db_session: Session, test_task):
    repo = ConversationRepository(db_session)
    return repo.create(
        parent_entity_type=ParentEntityType.TASK,
        parent_entity_id=test_task.id,
        agent_role=AgentRoleType.TASK_PLANNING,
        engine=AgentEngine.INTERNAL,
        model_id=None,
    )


def make_run(
    run_repo: BackgroundAgentRunRepository,
    agent: BackgroundAgent,
    conversation,
    *,
    triggered_by: str = "manual",
    status: BackgroundAgentRunStatus = BackgroundAgentRunStatus.COMPLETED,
    state_before: dict | None = None,
    state_after: dict | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
    started_at: datetime.datetime | None = None,
) -> BackgroundAgentRun:
    return run_repo.create(
        agent_id=agent.id,
        conversation_id=conversation.id,
        triggered_by=triggered_by,
        status=status,
        state_before=state_before or {},
        state_after=state_after,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        error=error,
        started_at=started_at,
    )


# ---------------------------------------------------------------------------
# BackgroundAgentRepository tests
# ---------------------------------------------------------------------------


class TestBackgroundAgentRepositoryCreate:
    def test_create_minimal(self, agent_repo: BackgroundAgentRepository, db_session: Session) -> None:
        a = agent_repo.create(name="Minimal", prompt="p", engine=AgentEngine.INTERNAL)
        assert a.id is not None
        assert a.name == "Minimal"
        assert a.enabled is True
        assert a.model_id is None
        assert a.description is None
        assert a.state == {}
        assert a.project_id is None

    def test_create_with_all_fields(self, agent_repo: BackgroundAgentRepository) -> None:
        a = agent_repo.create(
            name="Full",
            prompt="p",
            engine=AgentEngine.CLAUDE_CODE,
            description="desc",
            model_id="claude-3",
            enabled=False,
        )
        assert a.description == "desc"
        assert a.model_id == "claude-3"
        assert a.enabled is False
        assert a.engine == AgentEngine.CLAUDE_CODE


class TestBackgroundAgentRepositoryGetById:
    def test_get_existing(self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent) -> None:
        result = agent_repo.get_by_id(agent.id)
        assert result is not None
        assert result.id == agent.id

    def test_get_missing(self, agent_repo: BackgroundAgentRepository) -> None:
        assert agent_repo.get_by_id(99999) is None

    def test_get_with_triggers(self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent) -> None:
        agent_repo.add_event_trigger(agent.id, "task.created")
        agent_repo.add_schedule_trigger(agent.id, "0 9 * * *")

        result = agent_repo.get_by_id(agent.id, with_triggers=True)
        assert result is not None
        assert len(result.event_triggers) == 1
        assert len(result.schedule_triggers) == 1


class TestBackgroundAgentRepositoryGetAll:
    def test_get_all_no_filter(self, agent_repo: BackgroundAgentRepository, db_session: Session) -> None:
        agent_repo.create(name="A1", prompt="p", engine=AgentEngine.INTERNAL, enabled=True)
        agent_repo.create(name="A2", prompt="p", engine=AgentEngine.INTERNAL, enabled=False)
        results = agent_repo.get_all()
        assert len(results) >= 2

    def test_filter_enabled(self, agent_repo: BackgroundAgentRepository, db_session: Session) -> None:
        agent_repo.create(name="Enabled", prompt="p", engine=AgentEngine.INTERNAL, enabled=True)
        agent_repo.create(name="Disabled", prompt="p", engine=AgentEngine.INTERNAL, enabled=False)

        enabled = agent_repo.get_all(enabled=True)
        disabled = agent_repo.get_all(enabled=False)

        assert all(a.enabled for a in enabled)
        assert all(not a.enabled for a in disabled)


class TestBackgroundAgentRepositoryUpdate:
    def test_update_name(
        self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent, db_session: Session
    ) -> None:
        agent.name = "Updated Name"
        agent_repo.update(agent)
        db_session.expire(agent)
        refreshed = agent_repo.get_by_id(agent.id)
        assert refreshed is not None
        assert refreshed.name == "Updated Name"


class TestBackgroundAgentRepositoryDeleteById:
    def test_delete_existing(
        self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent, db_session: Session
    ) -> None:
        agent_id = agent.id
        agent_repo.delete_by_id(agent_id)
        assert agent_repo.get_by_id(agent_id) is None

    def test_delete_missing_is_noop(self, agent_repo: BackgroundAgentRepository) -> None:
        agent_repo.delete_by_id(99999)  # should not raise

    def test_delete_cascades_triggers(
        self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent, db_session: Session
    ) -> None:
        trigger = agent_repo.add_event_trigger(agent.id, "task.*")
        trigger_id = trigger.id
        agent_repo.delete_by_id(agent.id)
        assert db_session.get(BackgroundAgentEventTrigger, trigger_id) is None


class TestBackgroundAgentRepositoryGetAgentsForEventType:
    def test_match_exact(self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent) -> None:
        agent_repo.add_event_trigger(agent.id, "task.created")
        results = agent_repo.get_agents_for_event_type("task.created")
        assert any(a.id == agent.id for a in results)

    def test_no_match(self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent) -> None:
        agent_repo.add_event_trigger(agent.id, "task.created")
        results = agent_repo.get_agents_for_event_type("project.created")
        assert not any(a.id == agent.id for a in results)

    def test_disabled_agent_excluded(self, agent_repo: BackgroundAgentRepository, db_session: Session) -> None:
        disabled = agent_repo.create(name="Disabled", prompt="p", engine=AgentEngine.INTERNAL, enabled=False)
        agent_repo.add_event_trigger(disabled.id, "task.updated")
        results = agent_repo.get_agents_for_event_type("task.updated")
        assert not any(a.id == disabled.id for a in results)


class TestBackgroundAgentRepositoryUpdateState:
    def test_partial_merge(
        self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent, db_session: Session
    ) -> None:
        agent.state = {"key1": "val1", "key2": "val2"}
        agent_repo.update(agent)

        result = agent_repo.update_state(agent.id, {"key2": "updated", "key3": "new"})
        assert result is not None
        assert result.state == {"key1": "val1", "key2": "updated", "key3": "new"}

    def test_update_state_missing_agent(self, agent_repo: BackgroundAgentRepository) -> None:
        result = agent_repo.update_state(99999, {"k": "v"})
        assert result is None


class TestBackgroundAgentRepositoryTriggerCrud:
    def test_add_event_trigger(
        self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent, db_session: Session
    ) -> None:
        trigger = agent_repo.add_event_trigger(agent.id, "project.*")
        assert trigger.id is not None
        assert trigger.event_type_pattern == "project.*"
        assert trigger.agent_id == agent.id

    def test_remove_event_trigger(
        self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent, db_session: Session
    ) -> None:
        trigger = agent_repo.add_event_trigger(agent.id, "task.deleted")
        trigger_id = trigger.id
        agent_repo.remove_event_trigger(trigger_id)
        assert db_session.get(BackgroundAgentEventTrigger, trigger_id) is None

    def test_remove_missing_event_trigger_is_noop(self, agent_repo: BackgroundAgentRepository) -> None:
        agent_repo.remove_event_trigger(99999)  # should not raise

    def test_add_schedule_trigger(self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent) -> None:
        trigger = agent_repo.add_schedule_trigger(agent.id, "0 8 * * 1")
        assert trigger.id is not None
        assert trigger.cron_expression == "0 8 * * 1"
        assert trigger.last_triggered_at is None

    def test_remove_schedule_trigger(
        self, agent_repo: BackgroundAgentRepository, agent: BackgroundAgent, db_session: Session
    ) -> None:
        trigger = agent_repo.add_schedule_trigger(agent.id, "* * * * *")
        trigger_id = trigger.id
        agent_repo.remove_schedule_trigger(trigger_id)
        assert db_session.get(BackgroundAgentScheduleTrigger, trigger_id) is None


# ---------------------------------------------------------------------------
# BackgroundAgentRunRepository tests
# ---------------------------------------------------------------------------


class TestBackgroundAgentRunRepositoryCreate:
    def test_create_minimal(self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation) -> None:
        run = run_repo.create(
            agent_id=agent.id,
            conversation_id=conversation.id,
            triggered_by="manual",
            status=BackgroundAgentRunStatus.COMPLETED,
            state_before={},
        )
        assert run.id is not None
        assert run.triggered_by == "manual"
        assert run.status == BackgroundAgentRunStatus.COMPLETED
        assert run.state_before == {}
        assert run.state_after is None
        assert run.error is None
        assert run.input_tokens is None
        assert run.output_tokens is None

    def test_create_with_all_fields(
        self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)
        run = run_repo.create(
            agent_id=agent.id,
            conversation_id=conversation.id,
            triggered_by="event:42",
            status=BackgroundAgentRunStatus.FAILED,
            state_before={"counter": 1},
            started_at=now,
            completed_at=now,
            state_after={"counter": 2},
            trigger_event_id="42",
            input_tokens=100,
            output_tokens=200,
            error="Something failed",
        )
        assert run.trigger_event_id == "42"
        assert run.input_tokens == 100
        assert run.output_tokens == 200
        assert run.error == "Something failed"
        assert run.state_after == {"counter": 2}


class TestBackgroundAgentRunRepositoryGetById:
    def test_get_existing(self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation) -> None:
        run = make_run(run_repo, agent, conversation)
        result = run_repo.get_by_id(run.id)
        assert result is not None
        assert result.id == run.id

    def test_get_missing(self, run_repo: BackgroundAgentRunRepository) -> None:
        assert run_repo.get_by_id(99999) is None

    def test_get_with_agent(self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation) -> None:
        run = make_run(run_repo, agent, conversation)
        result = run_repo.get_by_id(run.id, with_agent=True)
        assert result is not None
        assert result.agent.id == agent.id


class TestBackgroundAgentRunRepositoryGetRunsForAgent:
    def test_returns_all_runs(
        self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation
    ) -> None:
        make_run(run_repo, agent, conversation)
        make_run(run_repo, agent, conversation)
        runs = run_repo.get_runs_for_agent(agent.id)
        assert len(runs) == 2

    def test_filter_by_status(
        self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation
    ) -> None:
        make_run(run_repo, agent, conversation, status=BackgroundAgentRunStatus.COMPLETED)
        make_run(run_repo, agent, conversation, status=BackgroundAgentRunStatus.FAILED)
        completed = run_repo.get_runs_for_agent(agent.id, status=BackgroundAgentRunStatus.COMPLETED)
        assert all(r.status == BackgroundAgentRunStatus.COMPLETED for r in completed)

    def test_limit_and_offset(
        self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation
    ) -> None:
        for _ in range(5):
            make_run(run_repo, agent, conversation)
        page1 = run_repo.get_runs_for_agent(agent.id, limit=2)
        page2 = run_repo.get_runs_for_agent(agent.id, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert {r.id for r in page1}.isdisjoint({r.id for r in page2})

    def test_ordered_by_started_at_desc(
        self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation
    ) -> None:
        base = datetime.datetime.now(datetime.UTC)
        make_run(run_repo, agent, conversation, started_at=base - datetime.timedelta(hours=2))
        make_run(run_repo, agent, conversation, started_at=base - datetime.timedelta(hours=1))
        make_run(run_repo, agent, conversation, started_at=base)
        runs = run_repo.get_runs_for_agent(agent.id)
        assert runs[0].started_at >= runs[1].started_at >= runs[2].started_at


class TestBackgroundAgentRunRepositoryGetLatestRun:
    def test_returns_most_recent(
        self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation
    ) -> None:
        base = datetime.datetime.now(datetime.UTC)
        make_run(run_repo, agent, conversation, started_at=base - datetime.timedelta(hours=1))
        latest_run = make_run(run_repo, agent, conversation, started_at=base)
        result = run_repo.get_latest_run(agent.id)
        assert result is not None
        assert result.id == latest_run.id

    def test_returns_none_for_no_runs(self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent) -> None:
        assert run_repo.get_latest_run(agent.id) is None


class TestBackgroundAgentRunRepositoryUpdate:
    def test_update_status(
        self,
        run_repo: BackgroundAgentRunRepository,
        agent: BackgroundAgent,
        conversation,
        db_session: Session,
    ) -> None:
        run = make_run(run_repo, agent, conversation, status=BackgroundAgentRunStatus.COMPLETED)
        run.status = BackgroundAgentRunStatus.FAILED
        run.error = "Revised"
        run_repo.update(run)
        db_session.expire(run)
        refreshed = run_repo.get_by_id(run.id)
        assert refreshed is not None
        assert refreshed.status == BackgroundAgentRunStatus.FAILED
        assert refreshed.error == "Revised"


class TestBackgroundAgentRunRepositoryGetStats:
    def test_empty_stats(self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent) -> None:
        stats = run_repo.get_stats(agent.id)
        assert stats["total_runs"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["avg_input_tokens"] is None
        assert stats["avg_output_tokens"] is None

    def test_aggregate_counts(
        self, run_repo: BackgroundAgentRunRepository, agent: BackgroundAgent, conversation
    ) -> None:
        make_run(
            run_repo, agent, conversation, status=BackgroundAgentRunStatus.COMPLETED, input_tokens=100, output_tokens=50
        )
        make_run(
            run_repo,
            agent,
            conversation,
            status=BackgroundAgentRunStatus.COMPLETED,
            input_tokens=200,
            output_tokens=100,
        )
        make_run(run_repo, agent, conversation, status=BackgroundAgentRunStatus.FAILED)
        make_run(run_repo, agent, conversation, status=BackgroundAgentRunStatus.CANCELLED)

        stats = run_repo.get_stats(agent.id)
        assert stats["total_runs"] == 4
        assert stats["completed"] == 2
        assert stats["failed"] == 1
        assert stats["avg_input_tokens"] == pytest.approx(150.0)
        assert stats["avg_output_tokens"] == pytest.approx(75.0)

    def test_cascade_delete_removes_runs(
        self,
        run_repo: BackgroundAgentRunRepository,
        agent: BackgroundAgent,
        conversation,
        db_session: Session,
    ) -> None:
        run = make_run(run_repo, agent, conversation)
        run_id = run.id
        db_session.delete(agent)
        db_session.flush()
        assert db_session.get(BackgroundAgentRun, run_id) is None
