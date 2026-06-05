# Worktree Management

**Navigation**: [Documentation Home](../INDEX.md) > [Architecture](./INDEX.md) > Worktree Management

## Overview

DevBoard manages a pool of git worktrees per codebase so that task agents always have an isolated working directory ready, without the latency of creating one on demand. The pool is represented by `WorktreeSlot` records; tasks lock a slot when an agent runs and release it when done.

**Location**: `backend/devboard/db/models/worktree_slot.py`

## WorktreeSlot Model

Each `WorktreeSlot` represents one working directory — either the main repository checkout or a git worktree branch. Key fields:

| Field | Description |
|-------|-------------|
| `codebase_id` | FK to the owning `Codebase` |
| `path` | Absolute filesystem path (unique) |
| `is_main_repo` | True for the primary checkout; at most one per codebase |
| `locked` | Whether a task currently holds this slot |
| `last_used_at` | Timestamp of last use; used for LRU selection |
| `last_used_by_task_id` | FK to the task that last used this slot |

## Slot Allocation

When a task needs a workspace (e.g., before running an implementation agent):

1. **Sticky reuse**: if the task previously used a slot and it is currently unlocked, that slot is preferred. This keeps the task's uncommitted state and checked-out branch intact across agent sessions.
2. **LRU fallback**: if no sticky slot is available, the least-recently-used unlocked slot is allocated.
3. **Lock**: the selected slot's `locked` flag is set and `last_used_by_task_id` is updated.

Tasks access their current workspace via `task.get_current_workspace_dir()`.

## Pool Size

The pool size (number of worktrees per codebase) is configurable per codebase. One slot is always the main repository (`is_main_repo=True`). Additional slots are git worktrees created at distinct paths.

## Worktree Lifecycle

Worktrees are created when slots are provisioned for a codebase and persist for the lifetime of the codebase configuration. They are not created/deleted per task — the pool is pre-allocated to avoid setup latency during agent execution.

Each worktree can be on a different branch. When a task is allocated a slot, the agent is responsible for checking out the appropriate branch before making changes.

## Sandbox Isolation

When agents run bash commands, the OS-level sandbox restricts filesystem writes to the allocated worktree path. This prevents agents from accidentally modifying the main repository or other task workspaces while still giving them full access to their own slot. See [Claude Code Integration](../4-ai-agents/claude-code-integration.md) for sandbox configuration details.

## Related Sections

- **[Database Schema](./database-schema.md)**: Full entity model
- **[Task Management](../2-features/task-management.md)**: How tasks use workspaces
- **[Claude Code Integration](../4-ai-agents/claude-code-integration.md)**: Sandbox configuration
