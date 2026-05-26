"""Tools for background agent state management and run history."""

import json
from typing import Annotated, Any

import toons
from pydantic import Field
from pydantic_ai import ModelRetry, Tool

from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.background_agent_run import BackgroundAgentRunStatus
from devboard.db.repositories.background_agent import BackgroundAgentRepository, BackgroundAgentRunRepository

# --- State tools ---


def create_read_state_tool(background_agent: BackgroundAgent) -> Tool:
    """Create a tool for reading the current agent's persistent state."""

    async def read_state() -> str:
        """Read the current agent's persistent state JSON.

        Returns:
            JSON string representation of the agent's state, or a message if empty.
        """
        if not background_agent.state:
            return "State is empty."
        return json.dumps(background_agent.state, indent=2)

    return Tool(function=read_state, name="read_state")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_update_state_tool(
    background_agent_repo: BackgroundAgentRepository,
    background_agent: BackgroundAgent,
) -> Tool:
    """Create a tool for updating the current agent's persistent state."""

    async def update_state(partial_state: dict[str, Any]) -> str:
        """Merge a partial update into the agent's persistent state.

        The update is applied immediately to the database and the in-memory
        agent object, ensuring consistency within the current run.

        Args:
            partial_state: Dict of keys/values to merge into agent.state

        Returns:
            Confirmation message with the updated keys.
        """
        if not partial_state:
            return "No changes provided."

        updated_agent = background_agent_repo.update_state(background_agent.id, partial_state)
        if updated_agent is None:
            raise ModelRetry(f"Failed to update state for agent {background_agent.id}.")

        # Also update the in-memory object to stay consistent within this run
        background_agent.state = {**background_agent.state, **partial_state}

        updated_keys = ", ".join(partial_state.keys())
        return f"State updated successfully. Modified keys: {updated_keys}"

    return Tool(function=update_state, name="update_state")  # ty:ignore[invalid-argument-type, invalid-return-type]


def create_read_agent_state_tool(background_agent_repo: BackgroundAgentRepository) -> Tool:
    """Create a tool for reading another background agent's state (read-only)."""

    async def read_agent_state(agent_id: int) -> str:
        """Read another background agent's state (read-only).

        Enables lightweight inter-agent coordination by allowing this agent
        to inspect the state of other background agents.

        Args:
            agent_id: The ID of the agent whose state to read.

        Returns:
            JSON string representation of the agent's state, or error if not found.
        """
        agent = background_agent_repo.get_by_id(agent_id)
        if agent is None:
            raise ModelRetry(f"Agent with ID {agent_id} not found.")

        if not agent.state:
            return f"Agent {agent_id} state is empty."

        return json.dumps(agent.state, indent=2)

    return Tool(function=read_agent_state, name="read_agent_state")  # ty:ignore[invalid-argument-type, invalid-return-type]


# --- Agent run tools ---


def _format_agent_runs_as_toon(runs: list[dict[str, Any]], limit: int) -> str:
    """Format agent runs as TOON-encoded output string."""
    if not runs:
        return "No agent runs found matching the filters."

    toon_output = toons.dumps(runs)

    if len(runs) == limit:
        return f"{toon_output}\n\nNote: {limit} results returned (the limit). There may be additional runs not shown — increase limit to see more."

    return toon_output


def create_query_agent_runs_tool(
    agent_run_repo: BackgroundAgentRunRepository, background_agent: BackgroundAgent
) -> Tool:
    """Create a tool for querying background agent run history."""

    async def query_agent_runs(
        agent_id: Annotated[
            int | None,
            Field(description="ID of the agent to query runs for. Defaults to the current agent if omitted."),
        ] = None,
        status: Annotated[
            str | None,
            Field(description='Filter by run status. Values: "queued", "running", "completed", "failed", "cancelled".'),
        ] = None,
        limit: Annotated[int, Field(description="Maximum number of runs to return, ordered most-recent first.")] = 20,
    ) -> str:
        """Query past execution runs for a background agent.

        Each run record includes the conversation_id (usable with conversation tools to
        retrieve the full run transcript), trigger details, start/end timestamps,
        token usage, and any error message. Use this to audit agent behaviour, diagnose
        failures, or track execution frequency.
        """
        resolved_agent_id = agent_id if agent_id is not None else background_agent.id

        status_enum: BackgroundAgentRunStatus | None = None
        if status is not None:
            try:
                status_enum = BackgroundAgentRunStatus(status.lower())
            except ValueError as e:
                valid = ", ".join(s.value for s in BackgroundAgentRunStatus)
                raise ModelRetry(f"Invalid status: '{status}'. Valid values: {valid}") from e

        runs = agent_run_repo.get_runs_for_agent(resolved_agent_id, status=status_enum, limit=limit)

        if not runs:
            return f"No runs found for agent {resolved_agent_id}."

        run_dicts = [
            {
                "id": run.id,
                "agent_id": run.agent_id,
                "status": run.status.value,
                "triggered_by": run.triggered_by,
                "conversation_id": run.conversation_id,
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "error": run.error,
            }
            for run in runs
        ]

        return _format_agent_runs_as_toon(run_dicts, limit)

    return Tool(function=query_agent_runs, name="query_agent_runs")  # ty:ignore[invalid-argument-type, invalid-return-type]
