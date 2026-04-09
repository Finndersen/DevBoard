"""Unit tests for BackgroundAgent, BackgroundAgentEventTrigger, BackgroundAgentScheduleTrigger models."""

from sqlalchemy.orm import Session

from devboard.agents.engines import AgentEngine
from devboard.db.models.background_agent import (
    BackgroundAgent,
    BackgroundAgentEventTrigger,
    BackgroundAgentScheduleTrigger,
)
from devboard.db.models.background_agent_run import BackgroundAgentRunStatus


class TestBackgroundAgent:
    """Tests for the BackgroundAgent model."""

    def test_create_agent(self, db_session: Session) -> None:
        agent = BackgroundAgent(
            name="Test Agent",
            prompt="You are a helpful agent.",
            engine=AgentEngine.INTERNAL,
        )
        db_session.add(agent)
        db_session.flush()

        assert agent.id is not None
        assert agent.name == "Test Agent"
        assert agent.engine == AgentEngine.INTERNAL
        assert agent.enabled is True
        assert agent.state == {}
        assert agent.model_id is None
        assert agent.description is None
        assert agent.project_id is None

    def test_agent_with_all_fields(self, db_session: Session) -> None:
        agent = BackgroundAgent(
            name="Full Agent",
            description="Does everything",
            prompt="You are an agent.",
            engine=AgentEngine.CLAUDE_CODE,
            model_id="anthropic:claude-sonnet-4",
            state={"key": "value"},
            enabled=False,
        )
        db_session.add(agent)
        db_session.flush()

        assert agent.description == "Does everything"
        assert agent.model_id == "anthropic:claude-sonnet-4"
        assert agent.state == {"key": "value"}
        assert agent.enabled is False

    def test_agent_event_trigger_relationship(self, db_session: Session) -> None:
        agent = BackgroundAgent(name="Trigger Agent", prompt="prompt", engine=AgentEngine.INTERNAL)
        db_session.add(agent)
        db_session.flush()

        trigger = BackgroundAgentEventTrigger(agent_id=agent.id, event_type_pattern="task.*")
        db_session.add(trigger)
        db_session.flush()

        db_session.refresh(agent)
        assert len(agent.event_triggers) == 1
        assert agent.event_triggers[0].event_type_pattern == "task.*"
        assert agent.event_triggers[0].agent_id == agent.id

    def test_agent_schedule_trigger_relationship(self, db_session: Session) -> None:
        agent = BackgroundAgent(name="Schedule Agent", prompt="prompt", engine=AgentEngine.INTERNAL)
        db_session.add(agent)
        db_session.flush()

        trigger = BackgroundAgentScheduleTrigger(agent_id=agent.id, cron_expression="0 9 * * *")
        db_session.add(trigger)
        db_session.flush()

        db_session.refresh(agent)
        assert len(agent.schedule_triggers) == 1
        assert agent.schedule_triggers[0].cron_expression == "0 9 * * *"
        assert agent.schedule_triggers[0].last_triggered_at is None

    def test_cascade_delete_triggers(self, db_session: Session) -> None:
        agent = BackgroundAgent(name="Cascade Agent", prompt="prompt", engine=AgentEngine.INTERNAL)
        db_session.add(agent)
        db_session.flush()

        event_trigger = BackgroundAgentEventTrigger(agent_id=agent.id, event_type_pattern="project.*")
        schedule_trigger = BackgroundAgentScheduleTrigger(agent_id=agent.id, cron_expression="* * * * *")
        db_session.add_all([event_trigger, schedule_trigger])
        db_session.flush()

        event_trigger_id = event_trigger.id
        schedule_trigger_id = schedule_trigger.id

        db_session.delete(agent)
        db_session.flush()

        assert db_session.get(BackgroundAgentEventTrigger, event_trigger_id) is None
        assert db_session.get(BackgroundAgentScheduleTrigger, schedule_trigger_id) is None

    def test_agent_run_status_values(self) -> None:
        assert BackgroundAgentRunStatus.QUEUED == "queued"
        assert BackgroundAgentRunStatus.RUNNING == "running"
        assert BackgroundAgentRunStatus.COMPLETED == "completed"
        assert BackgroundAgentRunStatus.FAILED == "failed"
        assert BackgroundAgentRunStatus.CANCELLED == "cancelled"


class TestBackgroundAgentEventTrigger:
    """Tests for the BackgroundAgentEventTrigger model."""

    def test_create_event_trigger(self, db_session: Session) -> None:
        agent = BackgroundAgent(name="Agent", prompt="prompt", engine=AgentEngine.INTERNAL)
        db_session.add(agent)
        db_session.flush()

        trigger = BackgroundAgentEventTrigger(agent_id=agent.id, event_type_pattern="task.created")
        db_session.add(trigger)
        db_session.flush()

        assert trigger.id is not None
        assert trigger.event_type_pattern == "task.created"
        assert trigger.created_at is not None
        assert trigger.agent is agent


class TestBackgroundAgentScheduleTrigger:
    """Tests for the BackgroundAgentScheduleTrigger model."""

    def test_create_schedule_trigger(self, db_session: Session) -> None:
        agent = BackgroundAgent(name="Agent", prompt="prompt", engine=AgentEngine.INTERNAL)
        db_session.add(agent)
        db_session.flush()

        trigger = BackgroundAgentScheduleTrigger(agent_id=agent.id, cron_expression="0 0 * * *")
        db_session.add(trigger)
        db_session.flush()

        assert trigger.id is not None
        assert trigger.cron_expression == "0 0 * * *"
        assert trigger.last_triggered_at is None
        assert trigger.created_at is not None
        assert trigger.agent is agent
