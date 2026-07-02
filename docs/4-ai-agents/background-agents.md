# Background Agents

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Background Agents

## Overview

Background agents are user-defined autonomous agents that run independently of the main task workflow. Unlike task agents that are tied to a specific task lifecycle, background agents can be triggered manually, on a cron schedule, or in response to system events — and can maintain persistent state across runs.

**Location**: `backend/devboard/agents/` (runner), `backend/devboard/db/models/background_agent.py` (models)

## Configuration

Each background agent has:

| Field | Description |
|-------|-------------|
| `name` | Display name |
| `description` | Optional description of purpose |
| `prompt` | Base system/task prompt for the agent |
| `engine` | Execution engine (INTERNAL, CLAUDE_CODE, GEMINI_CLI) |
| `model_id` | Optional model override; falls back to engine default |
| `enabled` | Whether the agent accepts triggers |
| `project_id` | Optional project association for context |
| `enabled_mcp_tools` | MCP tools the agent may use |
| `state` | Persistent JSON state, carried across runs |

## Trigger Types

Background agents support three trigger mechanisms, which can be combined on a single agent.

### Manual

Any agent can be triggered manually from the UI or API at any time. Useful for on-demand operations or testing before enabling automatic triggers.

### Scheduled (Cron)

An agent can have one or more `BackgroundAgentScheduleTrigger` records, each with a `cron_expression`. The scheduler fires each trigger independently, tracking `last_triggered_at` to avoid duplicate runs.

Example cron expressions:
- `0 9 * * 1-5` — weekday mornings at 09:00
- `*/30 * * * *` — every 30 minutes
- `0 0 * * *` — daily at midnight

### Event-Based

An agent can have one or more `BackgroundAgentEventTrigger` records, each with an `event_type_pattern`. When a system event is logged, all enabled event-triggered agents whose pattern matches the event type are queued for execution. The triggering `LogEntry` is passed to the agent as part of its initial message.

## Execution

When a background agent runs, `BackgroundAgentRunner`:

1. Creates a `Conversation` record linked to the agent
2. Creates a `BackgroundAgentRun` record with status `QUEUED`
3. Assembles the initial message containing:
   - Trigger type (`manual` / `schedule` / `event`)
   - The triggering event payload (for event triggers)
   - Any explicit input message (for manual triggers)
   - The agent's current `state` as JSON
4. Submits the run to `ConversationExecutionManager`

The agent's base `prompt` provides the system-level instructions; the assembled initial message provides the per-run context.

## Persistent State

The `state` field on `BackgroundAgent` is a JSON object that persists between runs. The agent can read its current state from the initial message and update it by using the state-update tool. This enables agents to track what they've already processed, accumulate summaries, or maintain counters.

Each `BackgroundAgentRun` records `state_before` and `state_after` snapshots for auditing.

## Run History

`BackgroundAgentRun` tracks each execution:

| Field | Description |
|-------|-------------|
| `status` | `queued` / `running` / `completed` / `failed` / `cancelled` |
| `triggered_by` | `manual`, `schedule`, or `event` |
| `trigger_event` | FK to the `LogEntry` that fired an event trigger |
| `started_at` / `completed_at` | Timing |
| `state_before` / `state_after` | State snapshots |
| `input_tokens` / `output_tokens` | Token usage |
| `error` | Error message if failed |
| `conversation` | Full conversation record for the run |

## UI

Background agents are managed in their own **top-level navigation section** at `/background-agents`:

- List view with status indicators (enabled/disabled, currently running)
- Create/edit form for agent configuration and triggers
- Run history with per-run conversation viewer
- Manual trigger button on the detail view

## MCP Tool Access

Background agents support the same MCP tool assignment as agent roles. Assign specific MCP server tools to an agent via `enabled_mcp_tools`. Only INTERNAL engine agents can use assigned MCP tools directly; Claude Code manages its own MCP configuration externally.

## Related Sections

- **[Agent Architecture](./agent-architecture.md)**: Engine and role system
- **[Configuration](./configuration.md)**: Engine and model configuration
- **[MCP Integration](../5-integrations/mcp-server.md)**: Assigning MCP tools to agents
