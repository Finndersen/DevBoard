"""BackgroundAgent and BackgroundAgentRun repositories for data access operations."""

import datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import joinedload, selectinload

from devboard.agents.engines import AgentEngine
from devboard.db.models.background_agent import (
    BackgroundAgent,
    BackgroundAgentEventTrigger,
    BackgroundAgentScheduleTrigger,
)
from devboard.db.models.background_agent_run import BackgroundAgentRun, BackgroundAgentRunStatus
from devboard.db.models.mcp_server import MCPTool
from devboard.db.repositories.base import BaseRepository


class BackgroundAgentRepository(BaseRepository[BackgroundAgent]):
    """Repository for BackgroundAgent data access operations."""

    def get_by_id(
        self,
        agent_id: int,
        *,
        with_triggers: bool = False,
        with_runs: bool = False,
    ) -> BackgroundAgent | None:
        """Get a background agent by ID with optional eager loading.

        Args:
            agent_id: The agent ID to look up
            with_triggers: If True, eager load event and schedule triggers
            with_runs: If True, eager load runs

        Returns:
            BackgroundAgent instance if found, None otherwise
        """
        stmt = select(BackgroundAgent).where(BackgroundAgent.id == agent_id)
        if with_triggers:
            stmt = stmt.options(
                selectinload(BackgroundAgent.event_triggers),
                selectinload(BackgroundAgent.schedule_triggers),
            )
        if with_runs:
            stmt = stmt.options(selectinload(BackgroundAgent.runs))
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_all(self, *, enabled: bool | None = None) -> list[BackgroundAgent]:
        """Get all background agents with optional enabled filter.

        Args:
            enabled: If provided, filter agents by enabled status

        Returns:
            List of BackgroundAgent instances
        """
        stmt = select(BackgroundAgent)
        if enabled is not None:
            stmt = stmt.where(BackgroundAgent.enabled == enabled)
        return list(self.db.execute(stmt).unique().scalars().all())

    def create(
        self,
        name: str,
        prompt: str,
        engine: AgentEngine,
        *,
        description: str | None = None,
        model_id: str | None = None,
        enabled: bool = True,
        project_id: int | None = None,
        mcp_tool_ids: list[int] | None = None,
    ) -> BackgroundAgent:
        """Create a new background agent.

        Args:
            name: Human-readable name for the agent
            prompt: System prompt defining agent behaviour
            engine: The execution engine to use
            description: Optional description
            model_id: Optional model identifier from LLMRegistry
            enabled: Whether the agent is active (default True)
            project_id: Optional project association
            mcp_tool_ids: Optional list of MCP tool IDs to associate

        Returns:
            Created BackgroundAgent instance
        """
        agent = BackgroundAgent(
            name=name,
            description=description,
            prompt=prompt,
            engine=engine,
            model_id=model_id,
            enabled=enabled,
            project_id=project_id,
        )
        if mcp_tool_ids:
            tools = list(self.db.execute(select(MCPTool).where(MCPTool.id.in_(mcp_tool_ids))).scalars().all())
            agent.enabled_mcp_tools = tools
        self.db.add(agent)
        self.db.flush()
        return agent

    def update(self, agent: BackgroundAgent) -> BackgroundAgent:
        """Update an existing background agent.

        Args:
            agent: BackgroundAgent instance with updated fields

        Returns:
            Updated BackgroundAgent instance
        """
        self.db.merge(agent)
        self.db.flush()
        return agent

    def delete_by_id(self, agent_id: int) -> None:
        """Hard delete a background agent by ID (cascade handles triggers + runs).

        Args:
            agent_id: ID of the agent to delete
        """
        agent = self.db.get(BackgroundAgent, agent_id)
        if agent is not None:
            self.db.delete(agent)
            self.db.flush()

    def get_agents_for_event_type(self, event_type: str) -> list[BackgroundAgent]:
        """Get enabled background agents that have an event trigger matching the given event type.

        Performs exact matching on event_type_pattern. Wildcard support can be added later.

        Args:
            event_type: The event type string to match against trigger patterns

        Returns:
            List of enabled BackgroundAgent instances with a matching trigger
        """
        stmt = (
            select(BackgroundAgent)
            .join(BackgroundAgentEventTrigger, BackgroundAgentEventTrigger.agent_id == BackgroundAgent.id)
            .where(
                BackgroundAgent.enabled == True,  # noqa: E712
                BackgroundAgentEventTrigger.event_type_pattern == event_type,
            )
            .distinct()
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def update_state(self, agent_id: int, state_patch: dict[str, Any]) -> BackgroundAgent | None:
        """Partially merge state_patch into the agent's current state.

        Args:
            agent_id: ID of the agent to update
            state_patch: Dict of keys/values to merge into agent.state

        Returns:
            Updated BackgroundAgent instance, or None if not found
        """
        agent = self.db.get(BackgroundAgent, agent_id)
        if agent is None:
            return None
        agent.state = {**agent.state, **state_patch}
        agent.updated_at = datetime.datetime.now(datetime.UTC)
        self.db.flush()
        return agent

    def add_event_trigger(self, agent_id: int, event_type_pattern: str) -> BackgroundAgentEventTrigger:
        """Add an event trigger to a background agent.

        Args:
            agent_id: ID of the agent
            event_type_pattern: Event type pattern to match

        Returns:
            Created BackgroundAgentEventTrigger instance
        """
        trigger = BackgroundAgentEventTrigger(agent_id=agent_id, event_type_pattern=event_type_pattern)
        self.db.add(trigger)
        self.db.flush()
        return trigger

    def remove_event_trigger(self, trigger_id: int) -> None:
        """Remove an event trigger by ID.

        Args:
            trigger_id: ID of the trigger to remove
        """
        trigger = self.db.get(BackgroundAgentEventTrigger, trigger_id)
        if trigger is not None:
            self.db.delete(trigger)
            self.db.flush()

    def add_schedule_trigger(self, agent_id: int, cron_expression: str) -> BackgroundAgentScheduleTrigger:
        """Add a schedule trigger to a background agent.

        Args:
            agent_id: ID of the agent
            cron_expression: Cron expression for the schedule

        Returns:
            Created BackgroundAgentScheduleTrigger instance
        """
        trigger = BackgroundAgentScheduleTrigger(agent_id=agent_id, cron_expression=cron_expression)
        self.db.add(trigger)
        self.db.flush()
        return trigger

    def remove_schedule_trigger(self, trigger_id: int) -> None:
        """Remove a schedule trigger by ID.

        Args:
            trigger_id: ID of the trigger to remove
        """
        trigger = self.db.get(BackgroundAgentScheduleTrigger, trigger_id)
        if trigger is not None:
            self.db.delete(trigger)
            self.db.flush()


class BackgroundAgentRunRepository(BaseRepository[BackgroundAgentRun]):
    """Repository for BackgroundAgentRun data access operations."""

    def create(
        self,
        agent_id: int,
        conversation_id: int,
        triggered_by: str,
        status: BackgroundAgentRunStatus,
        state_before: dict[str, Any],
        *,
        started_at: datetime.datetime | None = None,
        completed_at: datetime.datetime | None = None,
        state_after: dict[str, Any] | None = None,
        trigger_event_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        error: str | None = None,
    ) -> BackgroundAgentRun:
        """Create a run record.

        Args:
            agent_id: ID of the agent that ran
            conversation_id: ID of the associated conversation
            triggered_by: Trigger description e.g. "manual", "event:42", "schedule"
            status: Status of the run
            state_before: Snapshot of agent state at run start
            started_at: When the run started (defaults to now)
            completed_at: When the run completed
            state_after: Snapshot of agent state at run end
            trigger_event_id: Event ID if event-triggered
            input_tokens: Input token count
            output_tokens: Output token count
            error: Error message if failed

        Returns:
            Created BackgroundAgentRun instance
        """
        run = BackgroundAgentRun(
            agent_id=agent_id,
            conversation_id=conversation_id,
            triggered_by=triggered_by,
            status=status,
            state_before=state_before,
            started_at=started_at or datetime.datetime.now(datetime.UTC),
            completed_at=completed_at,
            state_after=state_after,
            trigger_event_id=trigger_event_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error=error,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def get_by_id(self, run_id: int, *, with_agent: bool = False) -> BackgroundAgentRun | None:
        """Get a run by ID with optional agent eager load.

        Args:
            run_id: The run ID to look up
            with_agent: If True, eager load the agent relationship

        Returns:
            BackgroundAgentRun instance if found, None otherwise
        """
        stmt = select(BackgroundAgentRun).where(BackgroundAgentRun.id == run_id)
        if with_agent:
            stmt = stmt.options(joinedload(BackgroundAgentRun.agent))
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_runs_for_agent(
        self,
        agent_id: int,
        *,
        status: BackgroundAgentRunStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[BackgroundAgentRun]:
        """Get runs for a background agent ordered by started_at descending.

        Args:
            agent_id: Agent ID to filter by
            status: Optional status filter
            limit: Optional max number of results
            offset: Optional number of results to skip

        Returns:
            List of BackgroundAgentRun instances
        """
        stmt = (
            select(BackgroundAgentRun)
            .where(BackgroundAgentRun.agent_id == agent_id)
            .order_by(BackgroundAgentRun.started_at.desc())
        )
        if status is not None:
            stmt = stmt.where(BackgroundAgentRun.status == status)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def get_latest_run(self, agent_id: int) -> BackgroundAgentRun | None:
        """Get the most recent run for a background agent.

        Args:
            agent_id: Agent ID to look up

        Returns:
            Most recent BackgroundAgentRun or None
        """
        stmt = (
            select(BackgroundAgentRun)
            .where(BackgroundAgentRun.agent_id == agent_id)
            .order_by(BackgroundAgentRun.started_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update(self, run: BackgroundAgentRun) -> BackgroundAgentRun:
        """Update an existing run record.

        Args:
            run: BackgroundAgentRun instance with updated fields

        Returns:
            Updated BackgroundAgentRun instance
        """
        self.db.merge(run)
        self.db.flush()
        return run

    def get_stats(self, agent_id: int) -> dict[str, Any]:
        """Get aggregate statistics for a background agent's runs.

        Args:
            agent_id: Agent ID to aggregate stats for

        Returns:
            Dict with total_runs, completed, failed, avg_input_tokens, avg_output_tokens
        """
        stmt = select(
            func.count(BackgroundAgentRun.id).label("total_runs"),
            func.sum(case((BackgroundAgentRun.status == BackgroundAgentRunStatus.COMPLETED, 1), else_=0)).label(
                "completed"
            ),
            func.sum(case((BackgroundAgentRun.status == BackgroundAgentRunStatus.FAILED, 1), else_=0)).label("failed"),
            func.avg(BackgroundAgentRun.input_tokens).label("avg_input_tokens"),
            func.avg(BackgroundAgentRun.output_tokens).label("avg_output_tokens"),
        ).where(BackgroundAgentRun.agent_id == agent_id)
        row = self.db.execute(stmt).one()
        total = row.total_runs or 0
        # SQLite returns booleans as 0/1 integers in aggregates, others may differ
        completed = int(row.completed or 0)
        failed = int(row.failed or 0)
        return {
            "total_runs": total,
            "completed": completed,
            "failed": failed,
            "avg_input_tokens": float(row.avg_input_tokens) if row.avg_input_tokens is not None else None,
            "avg_output_tokens": float(row.avg_output_tokens) if row.avg_output_tokens is not None else None,
        }
