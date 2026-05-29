"""Background agents API endpoints."""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select as sa_select

from devboard.agents.exceptions import ConversationBusyError
from devboard.agents.execution.background_agent_runner import BackgroundAgentRunner
from devboard.api.dependencies.repositories import (
    get_background_agent_or_404,
    get_background_agent_repository,
    get_background_agent_run_repository,
)
from devboard.api.dependencies.services import get_background_agent_runner
from devboard.api.schemas.background_agent import (
    BackgroundAgentCreate,
    BackgroundAgentEventTriggerResponse,
    BackgroundAgentResponse,
    BackgroundAgentRunResponse,
    BackgroundAgentRunStatsResponse,
    BackgroundAgentScheduleTriggerResponse,
    BackgroundAgentStateUpdate,
    BackgroundAgentUpdate,
    ManualTriggerRequest,
)
from devboard.db.models.background_agent import BackgroundAgent
from devboard.db.models.background_agent_run import BackgroundAgentRunStatus
from devboard.db.models.mcp_server import MCPTool
from devboard.db.repositories.background_agent import BackgroundAgentRepository, BackgroundAgentRunRepository

router = APIRouter()


def _agent_to_response(agent: BackgroundAgent, has_active_run: bool = False) -> BackgroundAgentResponse:
    return BackgroundAgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        prompt=agent.prompt,
        engine=agent.engine,
        model_id=agent.model_id,
        state=agent.state,
        enabled=agent.enabled,
        project_id=agent.project_id,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        mcp_tool_ids=[t.id for t in agent.enabled_mcp_tools],
        event_triggers=[BackgroundAgentEventTriggerResponse.model_validate(t) for t in agent.event_triggers],
        schedule_triggers=[BackgroundAgentScheduleTriggerResponse.model_validate(t) for t in agent.schedule_triggers],
        has_active_run=has_active_run,
    )


@router.post("/", response_model=BackgroundAgentResponse, status_code=201)
async def create_background_agent(
    data: BackgroundAgentCreate,
    repo: BackgroundAgentRepository = Depends(get_background_agent_repository),
) -> BackgroundAgentResponse:
    """Create a new background agent."""
    agent = repo.create(
        name=data.name,
        prompt=data.prompt,
        engine=data.engine,
        description=data.description,
        model_id=data.model_id,
        enabled=data.enabled,
        project_id=data.project_id,
        mcp_tool_ids=data.mcp_tool_ids or None,
    )
    for et in data.event_triggers:
        repo.add_event_trigger(agent.id, et.event_type_pattern)
    for st in data.schedule_triggers:
        repo.add_schedule_trigger(agent.id, st.cron_expression)

    repo.db.flush()
    # Re-fetch with triggers loaded
    agent = repo.get_by_id(agent.id, with_triggers=True)
    assert agent is not None
    has_active = repo.has_active_run(agent.id)
    return _agent_to_response(agent, has_active_run=has_active)


@router.get("/", response_model=list[BackgroundAgentResponse])
async def list_background_agents(
    enabled: bool | None = None,
    repo: BackgroundAgentRepository = Depends(get_background_agent_repository),
) -> list[BackgroundAgentResponse]:
    """List background agents, optionally filtered by enabled status."""
    agents = repo.get_all(enabled=enabled)
    running_ids = repo.get_running_agent_ids()
    return [_agent_to_response(a, has_active_run=a.id in running_ids) for a in agents]


@router.get("/{agent_id}", response_model=BackgroundAgentResponse)
async def get_background_agent(
    agent: BackgroundAgent = Depends(get_background_agent_or_404),
    repo: BackgroundAgentRepository = Depends(get_background_agent_repository),
) -> BackgroundAgentResponse:
    """Get a background agent by ID."""
    has_active = repo.has_active_run(agent.id)
    return _agent_to_response(agent, has_active_run=has_active)


@router.put("/{agent_id}", response_model=BackgroundAgentResponse)
async def update_background_agent(
    data: BackgroundAgentUpdate,
    agent: BackgroundAgent = Depends(get_background_agent_or_404),
    repo: BackgroundAgentRepository = Depends(get_background_agent_repository),
) -> BackgroundAgentResponse:
    """Update a background agent (full replacement of triggers and MCP tools)."""
    if data.name is not None:
        agent.name = data.name
    if data.description is not None:
        agent.description = data.description
    if data.prompt is not None:
        agent.prompt = data.prompt
    if data.engine is not None:
        agent.engine = data.engine
    if data.model_id is not None:
        agent.model_id = data.model_id
    if data.enabled is not None:
        agent.enabled = data.enabled
    if data.project_id is not None:
        agent.project_id = data.project_id

    if data.mcp_tool_ids is not None:
        tools = list(repo.db.execute(sa_select(MCPTool).where(MCPTool.id.in_(data.mcp_tool_ids))).scalars().all())
        agent.enabled_mcp_tools = tools

    if data.event_triggers is not None:
        # Replace all event triggers
        for trigger in list(agent.event_triggers):
            repo.remove_event_trigger(trigger.id)
        for et in data.event_triggers:
            repo.add_event_trigger(agent.id, et.event_type_pattern)

    if data.schedule_triggers is not None:
        # Replace all schedule triggers
        for trigger in list(agent.schedule_triggers):
            repo.remove_schedule_trigger(trigger.id)
        for st in data.schedule_triggers:
            repo.add_schedule_trigger(agent.id, st.cron_expression)

    repo.update(agent)
    repo.db.expire(agent)
    updated = repo.get_by_id(agent.id, with_triggers=True)
    assert updated is not None
    has_active = repo.has_active_run(updated.id)
    return _agent_to_response(updated, has_active_run=has_active)


@router.patch("/{agent_id}/state", response_model=BackgroundAgentResponse)
async def update_background_agent_state(
    data: BackgroundAgentStateUpdate,
    agent: BackgroundAgent = Depends(get_background_agent_or_404),
    repo: BackgroundAgentRepository = Depends(get_background_agent_repository),
) -> BackgroundAgentResponse:
    """Partially merge state into the background agent's persistent state."""
    repo.update_state(agent.id, data.state)
    repo.db.expire(agent)
    updated = repo.get_by_id(agent.id, with_triggers=True)
    assert updated is not None
    has_active = repo.has_active_run(updated.id)
    return _agent_to_response(updated, has_active_run=has_active)


@router.delete("/{agent_id}", status_code=204)
async def delete_background_agent(
    agent: BackgroundAgent = Depends(get_background_agent_or_404),
    repo: BackgroundAgentRepository = Depends(get_background_agent_repository),
) -> None:
    """Delete a background agent (cascades to triggers and runs)."""
    repo.delete_by_id(agent.id)


@router.post("/{agent_id}/trigger", response_model=BackgroundAgentRunResponse, status_code=201)
async def trigger_background_agent(
    agent: BackgroundAgent = Depends(get_background_agent_or_404),
    runner: BackgroundAgentRunner = Depends(get_background_agent_runner),
    request: ManualTriggerRequest | None = Body(default=None),
) -> BackgroundAgentRunResponse:
    """Manually trigger a background agent run.

    Creates a conversation and starts execution as a background task.
    Returns the created BackgroundAgentRun record.
    """
    input_message = request.input_message if request else None
    try:
        run = runner.trigger(
            agent,
            triggered_by="manual",
            input_message=input_message,
        )
    except ConversationBusyError as err:
        raise HTTPException(status_code=409, detail="An execution is already active for this conversation") from err
    return BackgroundAgentRunResponse.model_validate(run)


@router.get("/{agent_id}/runs", response_model=list[BackgroundAgentRunResponse])
async def list_background_agent_runs(
    status: BackgroundAgentRunStatus | None = None,
    limit: int | None = None,
    offset: int | None = None,
    agent: BackgroundAgent = Depends(get_background_agent_or_404),
    run_repo: BackgroundAgentRunRepository = Depends(get_background_agent_run_repository),
) -> list[BackgroundAgentRunResponse]:
    """List runs for a background agent."""
    runs = run_repo.get_runs_for_agent(agent.id, status=status, limit=limit, offset=offset)
    return [BackgroundAgentRunResponse.model_validate(r) for r in runs]


@router.get("/{agent_id}/runs/stats", response_model=BackgroundAgentRunStatsResponse)
async def get_background_agent_run_stats(
    agent: BackgroundAgent = Depends(get_background_agent_or_404),
    run_repo: BackgroundAgentRunRepository = Depends(get_background_agent_run_repository),
) -> BackgroundAgentRunStatsResponse:
    """Get aggregate run statistics for a background agent."""
    stats = run_repo.get_stats(agent.id)
    return BackgroundAgentRunStatsResponse(**stats)
