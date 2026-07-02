# Events Log

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > Events Log

## Overview

The Events Log is a **system-wide activity stream** that records all significant actions taken within DevBoard — by users, by the system itself, and by AI agents. It provides a unified audit trail and serves as both a monitoring tool and a trigger source for Background Agents.

## Events View

The Events view is accessible at the top level of the main navigation at `/events`. It displays a filterable, paginated stream of all log entries across the system.

### Event Sources

Every log entry has a `source` that identifies its origin:

- **Developer** (`developer`) — actions taken directly by the user (e.g. creating a task, updating a field)
- **System** (`system`) — automated system actions (e.g. state transitions, workflow events)
- **Agent** (`agent`) — actions performed by AI agents (e.g. writing a spec, completing an implementation step)

### Filtering

The Events view provides a rich filter bar:

- **Source toggle**: Filter to a single source type (Developer, System, or Agent) or view all
- **Project**: Scope entries to a specific project
- **Type**: Filter by event type prefix (e.g. `task.` matches all task-related events)
- **Pinned only**: Show only pinned entries
- **Date range**: Filter by `since` and `until` dates

Filters are synced to the URL query string, so filtered views can be bookmarked or shared.

### Pinned Entries

Entries can be pinned to mark them as important. Pinned entries display in a collapsible **Pinned** section at the top of the view, above the main feed. Pinned entries also respect the active source and project filters.

### Entry Status

Each log entry has a `status` field:

- **Active** — the default; the event is current and unresolved
- **Resolved** — the user has marked the event as resolved
- **Superseded** — the system has replaced this entry with a newer one

Users can mark active entries as resolved directly from the Events view using the row action button.

### Load More

The feed loads entries in pages. A "Load more" button appears at the bottom when additional entries are available. A manual Refresh button re-fetches from the top.

## Entry Scoping

Log entries can be scoped to a **project**, a **task**, or both (task entries are implicitly project-scoped via the task's project). The Project / Task column in the Events view shows these associations with navigation links.

The project-scoped subset of the event log is also accessible from the **Events tab** on the Project Detail view — see [Project Management](./project-management.md).

## Background Agent Integration

The event log doubles as a **trigger source** for event-driven Background Agents. When a new log entry is created, the system checks all background agents configured with an `event_type_pattern`. If the entry's `type` matches the pattern, the background agent is queued for execution with the triggering entry supplied as context.

This allows background agents to react automatically to system events — for example, kicking off a review workflow whenever a task moves to `PR_OPEN`, or sending a notification whenever an agent completes an implementation step.

See [Background Agents](../4-ai-agents/background-agents.md) for details on configuring event-triggered agents.
