# Claude Code Session Viewer

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > Claude Code Session Viewer

**Purpose**: Browse, search, and inspect Claude Code conversation sessions from the DevBoard UI, with task association links for sessions tied to DevBoard tasks.

## Overview

The Claude Code Session Viewer provides a read-only interface for exploring Claude Code sessions stored in `~/.claude/projects/`. Sessions are organized by project (working directory) and displayed with metadata such as last activity, file size, and task associations. Clicking a session loads its full conversation history.

## Session List View

Sessions for a selected project are listed in the `SessionListPanel` with:

- **Label**: First user message extracted from the session JSONL file (truncated to 200 characters)
- **Relative timestamp**: e.g. "5m ago", "2h ago", "3d ago"
- **File size**: Size of the JSONL file on disk
- **Plan + Implement badge**: Shown when `session_role = "plan"` (i.e. the session has a linked implementation session)
- **Task association**: When a session is linked to a DevBoard task via a `Conversation` record, a clickable link displays the task title and agent role stage, navigating to the task detail view

Sessions with `session_role = "implementation"` are hidden from the list (they are surfaced implicitly through the linked planning session).

## Task Association

Each Claude Code session may be linked to **at most one** DevBoard task. The link is established via the `Conversation` database record which stores the `external_session_id` (the Claude Code session ID) and references a parent `Task` via the polymorphic `parent_entity_type` / `parent_entity_id` fields.

When a session is linked to a task, the session list entry shows:

- **Task title**: Clickable link navigating to `/tasks/{task_id}`
- **Agent role badge**: Human-readable label for the task stage:
  - `task_planning` → `Planning`
  - `task_implementation` → `Implementation`
  - `task_pr_review` → `PR Review`

Only top-level conversations (no `parent_conversation_id`) linked to tasks are shown — sub-agent conversations are excluded.

## Search

The session search bar uses ripgrep to search JSONL files across all projects or within the currently selected project. Matching sessions are highlighted with a match-count badge. Search results filter the visible session list.

## API Endpoints

All endpoints are under `/api/claude-code/`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/projects` | List all Claude Code projects with metadata |
| `GET` | `/projects/{encoded_path}/sessions` | List sessions for a project, enriched with task info |
| `GET` | `/sessions/{session_id}/messages` | Full conversation event history for a session |
| `GET` | `/sessions/search` | Ripgrep search across session JSONL files |

The `list_sessions` endpoint performs a batch lookup of task associations for all sessions in one query (keyed by `external_session_id`) before constructing the response.

### Session Response Schema

```json
{
  "session_id": "abc123",
  "label": "Fix the authentication bug",
  "last_activity": "2026-03-07T12:00:00Z",
  "file_size": 4096,
  "is_empty": false,
  "linked_session_id": null,
  "session_role": null,
  "task_info": {
    "task_id": 42,
    "task_title": "Fix authentication bug",
    "agent_role": "task_implementation"
  }
}
```

`task_info` is `null` when the session has no associated DevBoard task.

## Database

An index on `conversations.external_session_id` (`idx_conversation_external_session_id`) supports efficient batch lookup of task associations by session ID.

## Files

**Backend**:
- `backend/devboard/api/routers/claude_code.py`: API endpoints
- `backend/devboard/api/schemas/claude_code.py`: Response schemas (`ClaudeCodeSessionResponse`, `SessionTaskInfoResponse`)
- `backend/devboard/db/repositories/conversation.py`: `get_task_info_by_session_ids()` repository method
- `backend/devboard/agents/engines/claude_code/session/manager.py`: `ClaudeSessionManager` — reads session JSONL files from disk

**Frontend**:
- `frontend/src/components/claude-code/SessionListPanel.tsx`: Session list with task link rendering
- `frontend/src/lib/api.ts`: `ClaudeCodeSession` and `SessionTaskInfo` TypeScript interfaces
