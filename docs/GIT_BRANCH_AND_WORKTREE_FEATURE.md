# Git Branch and Worktree Management Feature Specification

## Overview

This feature enables DevBoard to manage git branches and worktrees for tasks, supporting both sequential development (one task at a time) and parallel development (multiple tasks simultaneously).

**Core Principle**: Every task is associated with a git branch. Worktrees are dynamically allocated from a pool to enable task parallelism without branch switching overhead.

---

## Key Concepts

### 1. Task-Branch Association

**Every task has a git branch** - no exceptions when git integration is enabled.

- **Task lifecycle**: Branch created at task creation, merged when task completes
- **Branch persistence**: Branch exists for entire task lifetime, across multiple conversations
- **Branch modes**:
  - `CREATE_NEW`: Create new branch from base branch
  - `USE_EXISTING`: Link task to pre-existing branch

### 2. Worktree Pool

A **pool of working directories** (including the main repository checkout) that can be dynamically allocated to tasks.

**Pool composition**:
- **Slot 0**: Main repository checkout (e.g., `/projects/myapp`)
- **Slot 1-N**: Additional worktrees (e.g., `/projects/myapp.worktree-1`, `/projects/myapp.worktree-2`)

**Pool behavior**:
- Slots can be locked by tasks (when agent is running)
- Slots can be reused by different tasks (checkout different branch)
- Pool grows dynamically when all slots are locked and more parallelism is needed

### 3. Task Stickiness

**Tasks prefer to reuse the same worktree slot** to minimize branch switching:

1. Task A used slot 2 last time → prefer slot 2 if available
2. Slot 2 already has Task A's branch checked out → no git operation needed
3. Slot 2 has different branch → checkout Task A's branch

**Benefits**: Reduced branch switching, predictable workspace locations, better UX

---

## Data Model

### Task Model (Enhanced)

```python
class Task(Base):
    # ... existing fields (id, project_id, codebase_id, title, status, etc.) ...

    # Git branch configuration
    branch_name: str  # Required! e.g., "feature/task-123-add-auth"
    branch_mode: BranchMode  # CREATE_NEW | USE_EXISTING
    base_branch: str = "main"  # Branch to merge back to
```

**Design decisions**:
- `branch_name` is required (not optional) - every task has a branch
- `base_branch` stored explicitly to know merge target (can't be derived from git)
- No `worktree_id` - worktree allocation is transient, not persisted on task

### WorktreeSlot Model (New)

```python
class WorktreeSlot(Base):
    """A slot in the worktree pool for a codebase"""
    id: UUID
    codebase_id: UUID
    path: str  # e.g., "/projects/myapp" or "/projects/myapp.worktree-1"
    is_main_repo: bool  # True for slot 0 (main checkout)

    # Current lock state (nullable = available)
    locked_by_task_id: Optional[UUID]  # Task currently using this slot
    locked_at: Optional[datetime]
    current_branch: Optional[str]  # Last known checked-out branch

    # Stickiness tracking
    last_used_at: datetime
    last_used_by_task_id: Optional[UUID]  # For preference on next allocation

    created_at: datetime
```

**Key insights**:
- Lock is per **task** (not conversation) - aligns with branch ownership
- Stale lock detection: Check if task has active conversations
- `current_branch` tracked for optimization (avoid unnecessary checkouts)
- Single table (no separate WorktreeLock table)

### Codebase Model (Enhanced)

```python
class Codebase(Base):
    # ... existing fields ...

    # Optional git integration features (future)
    git_integration_enabled: bool = False
    git_hooks_installed: bool = False
```

---

## User Workflows

### Workflow 1: Task Creation with Git Branch

**UI - Create Task Form**:

```
Create New Task
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title: Add user authentication
Project: [DevBoard v2 ▼]
Codebase: [/projects/devboard ▼]

Git Branch Configuration:
  ● Create new branch
    Branch name: [Auto-generate ▼] feature/task-abc123-add-user-auth
    Base branch: [main ▼]

  ○ Use existing branch: [Select branch ▼]

[Create Task]
```

**Branch name options**:
- **Auto-generate**: Template-based `feature/task-{id}-{slug}`
- **LLM-generate** (future): AI suggests semantic name based on title
- **Custom**: User enters branch name manually

**What happens**:
1. Task record created with `branch_name` and `branch_mode`
2. If `CREATE_NEW`: Git branch created immediately (not deferred)
3. Branch is **not** checked out in main repo (avoids conflicts with user's current work)
4. Task can enter PLANNING phase - agent will allocate worktree when needed

### Workflow 2: Starting Planning/Implementation Agent

**User action**: Click "Start Planning" or "Start Implementation" button

**System workflow**:
```
1. WorkspaceAllocationService.allocate_for_task(task_id):

   a. Find preferred slot:
      - Check: Did this task use a slot recently? (stickiness)
      - Check: Is any slot already on this task's branch? (optimization)
      - Fallback: Pick least-recently-used available slot

   b. Handle allocation:
      - If slot available:
        * Lock slot by task
        * Checkout task's branch in that slot (if not already)
        * Return slot path to agent

      - If all slots locked:
        * Prompt user: "Create new worktree? All slots in use."
        * If yes: Create new worktree, add to pool, lock it
        * If no: Wait or stop another task

2. Agent starts:
   - working_directory = allocated slot path
   - Branch is already checked out (no manual switching needed)
   - Agent makes changes, commits, etc.

3. Agent stops:
   - Release slot lock
   - Slot remains in pool for reuse
   - Task preference remembered for next time
```

### Workflow 3: Parallel Task Development

**Scenario**: User wants to work on 3 tasks simultaneously

**Setup**:
```
Task 1: "Add login"        → branch: feature/task-1-login
Task 2: "Add password"     → branch: feature/task-2-password
Task 3: "Add OAuth"        → branch: feature/task-3-oauth
```

**Execution**:
```
User starts Task 1 implementation:
  → Allocates slot 0 (main repo), checkout feature/task-1-login
  → Agent 1 running in /projects/myapp

User starts Task 2 implementation:
  → All slots locked, prompt to create worktree
  → Creates slot 1: /projects/myapp.worktree-1
  → Checkout feature/task-2-password
  → Agent 2 running in /projects/myapp.worktree-1

User starts Task 3 implementation:
  → All slots locked, prompt to create worktree
  → Creates slot 2: /projects/myapp.worktree-2
  → Checkout feature/task-3-oauth
  → Agent 3 running in /projects/myapp.worktree-2

All 3 agents work in parallel, no conflicts!
```

**Later** (after Task 1 completes):
```
User starts Task 4 implementation:
  → Slot 0 available (Task 1 done)
  → Reuse slot 0, checkout feature/task-4-newfeature
  → No new worktree needed!
```

### Workflow 4: Task Completion and Cleanup

**Merging and cleanup**:

```
UI - Task Detail (when status = COMPLETE):
┌─────────────────────────────────────────┐
│ Task: Add user authentication           │
│ Status: COMPLETE ✓                      │
│                                          │
│ Git Status:                              │
│ • Branch: feature/task-123-auth         │
│ • Commits ahead: 12                     │
│ • Ready to merge                        │
│                                          │
│ [Merge to main] [Delete Branch]         │
└─────────────────────────────────────────┘
```

**Merge operation**:
1. Merge `task.branch_name` into `task.base_branch`
2. Handle conflicts (show in UI if any)
3. Optionally delete branch after successful merge
4. If worktree was used, can optionally cleanup (but not required - can reuse)

---

## Worktree Management

### Worktree Location Strategy

**Sibling directory approach** (user-friendly):

```
/Users/dev/projects/
├── devboard/                      # Main repository (slot 0)
│   ├── .git/
│   └── src/
├── devboard.worktree-1/           # Worktree slot 1
│   ├── .git → ../devboard/.git/worktrees/worktree-1/
│   └── src/
└── devboard.worktree-2/           # Worktree slot 2
    ├── .git → ../devboard/.git/worktrees/worktree-2/
    └── src/
```

**Benefits**:
- Easily discoverable in file browser
- Simple naming convention
- Can open in IDE (File → Open Folder)
- Shareable paths for team collaboration

**Naming convention**:
```python
def get_worktree_path(codebase: Codebase, slot_number: int) -> Path:
    """Generate worktree path as sibling to main repo"""
    codebase_path = Path(codebase.local_path)
    parent = codebase_path.parent
    base_name = codebase_path.name
    return parent / f"{base_name}.worktree-{slot_number}"
```

### Worktree Performance Considerations

**Creation time**: For large repositories (10GB+, 100k files), worktree creation can take 30+ seconds.

**Mitigation strategies**:
1. **Make worktrees optional**: Default to single-task workflow (no worktrees needed)
2. **Show progress**: "Creating worktree... this may take a minute"
3. **Create in background**: Non-blocking UI
4. **Pool reuse**: Don't delete worktrees unnecessarily - keep for reuse
5. **Future**: Sparse checkout for monorepos (only checkout relevant subdirectories)

**User control**:
```
Settings → Workspace:
  Max worktrees: [3]  (0 = unlimited)
  Auto-create worktrees: [Prompt me ▼]  (Always | Never | Prompt)
  Cleanup unused worktrees: [After 7 days ▼]
```

### Worktree Branch Switching

**Yes, you can checkout different branches in a worktree!**

This enables efficient reuse:
```bash
# Worktree initially on branch A
cd /projects/myapp.worktree-1
git status  # On branch feature/task-1-login

# Task 1 completes, Task 4 starts
git checkout feature/task-4-newfeature  # Reuse same worktree!
```

**In DevBoard**:
- Slot allocated to Task 4
- System runs: `git checkout feature/task-4-newfeature` in slot path
- Updates `WorktreeSlot.current_branch` in DB
- Agent starts in reused worktree

---

## Worktree Allocation Algorithm

### Smart Allocation with Stickiness

```python
async def allocate_worktree_for_task(task_id: UUID) -> WorktreeSlot:
    """
    Allocate a worktree slot for task, with preference for previously-used slot.
    """
    task = await task_repo.get(task_id)

    # Strategy 1: Task stickiness - prefer last-used slot
    preferred_slot = await slot_repo.find_one(
        codebase_id=task.codebase_id,
        last_used_by_task_id=task.id,
        locked_by_task_id=None  # Must be available
    )
    if preferred_slot:
        return await lock_and_prepare_slot(preferred_slot, task)

    # Strategy 2: Branch optimization - slot already on correct branch
    optimized_slot = await slot_repo.find_one(
        codebase_id=task.codebase_id,
        current_branch=task.branch_name,
        locked_by_task_id=None
    )
    if optimized_slot:
        return await lock_and_prepare_slot(optimized_slot, task)

    # Strategy 3: LRU - pick least recently used available slot
    lru_slot = await slot_repo.find_oldest_available(
        codebase_id=task.codebase_id,
        locked_by_task_id=None
    )
    if lru_slot:
        return await lock_and_prepare_slot(lru_slot, task)

    # Strategy 4: No slots available - prompt user
    raise AllSlotsLockedException(
        message="All worktrees are currently in use",
        locked_by_tasks=await get_locking_tasks(task.codebase_id),
        can_create_new=True
    )

async def lock_and_prepare_slot(slot: WorktreeSlot, task: Task) -> WorktreeSlot:
    """Lock slot and ensure correct branch is checked out"""

    # Checkout branch if different
    if slot.current_branch != task.branch_name:
        git = CodebaseIntegration(get_repo_path_for_slot(slot))
        git.checkout_branch(task.branch_name)

    # Acquire lock
    slot.locked_by_task_id = task.id
    slot.locked_at = datetime.utcnow()
    slot.current_branch = task.branch_name
    slot.last_used_at = datetime.utcnow()
    slot.last_used_by_task_id = task.id

    await slot_repo.update(slot)
    return slot
```

### Slot Lifecycle

```
1. Bootstrap (first task for codebase):
   - No slots exist yet
   - Create slot 0 (main repo path, is_main_repo=True)
   - Lock it for task

2. Second concurrent task:
   - Slot 0 locked
   - Prompt: "Create worktree?"
   - Create slot 1 (worktree path, is_main_repo=False)
   - Add to pool
   - Lock it for task

3. First task completes:
   - Release slot 0 lock
   - Slot 0 now available for reuse

4. Third task starts:
   - Slot 0 available
   - Reuse slot 0 (checkout different branch)
   - No new worktree needed

5. Long-term:
   - Pool stabilizes at size = max concurrency
   - Slots reused efficiently
   - Inactive worktrees cleaned up periodically
```

---

## Lock Management

### Acquiring Lock

```python
# When agent starts
slot = await allocate_worktree_for_task(task.id)

# Slot is now:
# - locked_by_task_id = task.id
# - locked_at = now
# - current_branch = task.branch_name
# - last_used_at = now
# - last_used_by_task_id = task.id
```

### Releasing Lock

```python
# When agent stops (completion, error, manual stop)
await unlock_slot(slot.id)

# Slot is now:
# - locked_by_task_id = NULL
# - locked_at = NULL
# - current_branch = still set (for next allocation optimization)
# - last_used_at = still set (for LRU)
# - last_used_by_task_id = still set (for stickiness)
```

### Stale Lock Detection

**Problem**: Locks can become stale if:
- Agent crashes
- Server restarts
- User force-quits browser

**Solution**: Detect and cleanup stale locks

```python
async def cleanup_stale_locks():
    """Remove locks for tasks with no active conversations"""
    locked_slots = await slot_repo.get_all_locked()

    for slot in locked_slots:
        task = await task_repo.get(slot.locked_by_task_id)

        # Check if task has any active conversations
        active_conversations = await conversation_repo.find_active_for_task(task.id)

        if not active_conversations:
            # No active conversations - lock is stale
            await unlock_slot(slot.id)

        # Also check age-based failsafe
        if slot.locked_at < datetime.utcnow() - timedelta(hours=24):
            # Lock older than 24h - definitely stale
            await unlock_slot(slot.id)
```

**Run cleanup**:
- On server startup (reconcile state)
- Before allocation attempts (ensure accurate availability)
- Background task every 5 minutes (proactive cleanup)

---

## State Reconciliation

### On Server Startup

**Problem**: DB state may diverge from actual git state if:
- Worktrees deleted manually
- Branches deleted externally
- Server crashed mid-operation

**Solution**: Reconcile DB with git reality

```python
async def reconcile_worktree_state_on_startup():
    """Sync DB with actual git worktree state for all codebases"""

    codebases = await codebase_repo.get_all()

    for codebase in codebases:
        git = CodebaseIntegration(codebase.local_path)

        # Get actual worktrees from git
        actual_worktrees = git.list_worktrees()  # git worktree list --porcelain

        # Get DB slots
        db_slots = await slot_repo.get_by_codebase(codebase.id)

        # Cleanup: Remove DB slots for deleted worktrees
        for slot in db_slots:
            if not slot.is_main_repo:
                exists = any(wt.path == slot.path for wt in actual_worktrees)
                if not exists:
                    await slot_repo.delete(slot.id)

        # Discovery: Add DB slots for manually-created worktrees
        for wt in actual_worktrees:
            if is_devboard_worktree(wt.path):  # Check naming convention
                exists = any(s.path == wt.path for s in db_slots)
                if not exists:
                    await slot_repo.create(
                        codebase_id=codebase.id,
                        path=wt.path,
                        is_main_repo=False,
                        current_branch=wt.branch
                    )

        # Cleanup: Release all locks (conservative - safe on restart)
        for slot in db_slots:
            if slot.locked_by_task_id:
                await unlock_slot(slot.id)
```

---

## API Design

### Task APIs (Enhanced)

```
POST /api/tasks/
Body:
{
  "title": "Add user authentication",
  "project_id": "uuid",
  "codebase_id": "uuid",
  "branch_name": "feature/add-user-auth",  # Required
  "branch_mode": "CREATE_NEW",             # Required
  "base_branch": "main"                    # Optional, defaults to "main"
}
Response: { task: {...}, branch_created: true }

GET /api/tasks/{id}/git-status
Response:
{
  "branch_name": "feature/task-123-auth",
  "branch_exists": true,
  "base_branch": "main",
  "commits_ahead": 5,
  "commits_behind": 0,
  "can_merge": true,
  "has_conflicts": false,
  "worktree_slot": {
    "id": "slot-2",
    "path": "/projects/myapp.worktree-1",
    "locked": true,
    "locked_since": "2025-10-21T14:30:00Z"
  }
}

POST /api/tasks/{id}/merge-branch
Body: {
  "target_branch": "main",  # Optional, defaults to task.base_branch
  "delete_branch": true
}
Response: { success: true, merge_commit: "abc123..." }
```

### Worktree Pool APIs

```
GET /api/codebases/{id}/worktree-pool
Response:
{
  "codebase_id": "uuid",
  "codebase_path": "/projects/myapp",
  "slots": [
    {
      "id": "slot-1",
      "path": "/projects/myapp",
      "is_main_repo": true,
      "status": "locked",
      "locked_by_task": {
        "id": "task-1",
        "title": "Add login",
        "branch": "feature/task-1-login"
      },
      "locked_at": "2025-10-21T14:30:00Z"
    },
    {
      "id": "slot-2",
      "path": "/projects/myapp.worktree-1",
      "is_main_repo": false,
      "status": "available",
      "current_branch": "feature/task-3-api",
      "last_used_at": "2025-10-21T13:15:00Z"
    }
  ],
  "stats": {
    "total_slots": 2,
    "available": 1,
    "locked": 1
  }
}

POST /api/codebases/{id}/worktree-pool/slots
Body: {
  "branch": "feature/task-5-ui"  # Optional - branch to checkout
}
Response: {
  "slot": { "id": "slot-3", "path": "/projects/myapp.worktree-2", ... },
  "created": true
}

DELETE /api/worktree-slots/{id}
Response: { success: true }
# Error if slot is locked
```

### Workspace Allocation API

```
POST /api/tasks/{id}/allocate-workspace
Response (success):
{
  "slot": {
    "id": "slot-2",
    "path": "/projects/myapp.worktree-1",
    "is_main_repo": false
  },
  "branch_checked_out": true,
  "ready": true
}

Response (all locked):
{
  "error": "ALL_SLOTS_LOCKED",
  "locked_by": [
    { "task_id": "task-1", "title": "Add login", "slot": "main repo" },
    { "task_id": "task-3", "title": "Add API", "slot": "worktree-1" }
  ],
  "can_create_new": true
}
```

---

## Agent Integration

### Agent Initialization

```python
async def start_task_agent(task_id: UUID, conversation_id: UUID):
    """Start planning or implementation agent for task"""

    task = await task_repo.get(task_id)

    # Allocate workspace
    try:
        slot = await workspace_service.allocate_for_task(task_id)
    except AllSlotsLockedException as e:
        # Prompt user or auto-create based on settings
        if user_settings.auto_create_worktrees:
            slot = await workspace_service.create_and_lock_slot(task)
        else:
            raise  # Return to UI for user decision

    # Agent works in allocated slot
    working_directory = slot.path

    # Start agent (Claude Code, Gemini CLI, or internal)
    agent = create_agent(
        conversation_id=conversation_id,
        working_directory=working_directory,
        initial_context={
            "task": task,
            "branch": task.branch_name,
            "workspace_type": "main repo" if slot.is_main_repo else "worktree"
        }
    )

    # Agent runs...

    # On completion/stop
    await workspace_service.release_slot(slot.id)
```

### Agent State Validation

**Detect unexpected branch changes during agent execution**:

```python
class ClaudeCodeAgent:
    def __init__(self, working_directory: str, expected_branch: str):
        self.working_directory = working_directory
        self.expected_branch = expected_branch
        self._validate_state()

    def _validate_state(self):
        """Ensure we're on the correct branch"""
        git = CodebaseIntegration(self.working_directory)
        actual_branch = git.get_current_branch()

        if actual_branch != self.expected_branch:
            raise AgentStateError(
                f"Branch mismatch in {self.working_directory}\n"
                f"Expected: {self.expected_branch}\n"
                f"Actual: {actual_branch}\n"
                f"Did you manually switch branches?"
            )

    async def execute_operation(self, operation):
        # Validate before each operation
        self._validate_state()

        # Perform operation
        result = await operation.execute()

        # Validate after
        self._validate_state()

        return result
```

---

## Frontend UI

### Task Creation Form

```
Create New Task
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Title: ___________________________________________
      Add user authentication

Project: [DevBoard v2                          ▼]
Codebase: [/projects/devboard                   ▼]

Git Branch Configuration:
  ● Create new branch
    Branch name: [Auto-generate ▼] feature/task-abc123-add-user-auth
                                     └─ [Generate with AI] button
    Base branch: [main ▼]

  ○ Use existing branch
    Select branch: [                            ▼]
                    └─ Populated from git branch list

                                [Cancel] [Create Task]
```

### Task Detail - Git Status Panel

```
┌─ Git Information ────────────────────────────────┐
│                                                   │
│ Branch: feature/task-123-add-user-auth           │
│ Base: main                                       │
│ Status: ↑ 5 commits ahead, ↓ 0 behind           │
│                                                   │
│ Workspace:                                       │
│ • Path: /projects/devboard.worktree-1/           │
│ • Status: 🔒 Locked (Agent running)              │
│ • Since: 2 minutes ago                           │
│                                                   │
│ [Open in VS Code] [Open Terminal]                │
│                                                   │
│ Actions:                                         │
│ [View Changes] [Merge to main] [Delete Branch]   │
│                                                   │
└───────────────────────────────────────────────────┘
```

### Worktree Pool Status (Settings or Codebase view)

```
Codebase: /projects/devboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Worktree Pool (2 slots, 1 available):

┌─ Slot 0: Main Repository ────────────────────────┐
│ Path: /projects/devboard                          │
│ Status: 🔒 LOCKED                                 │
│ Task: Add user authentication (task-123)          │
│ Branch: feature/task-123-add-user-auth            │
│ Locked: 15 minutes ago                            │
│                                                    │
│ [View Task] [Force Unlock]                        │
└────────────────────────────────────────────────────┘

┌─ Slot 1: Worktree 1 ──────────────────────────────┐
│ Path: /projects/devboard.worktree-1                │
│ Status: ✓ AVAILABLE                                │
│ Last used: 2 hours ago                             │
│ Last branch: feature/task-456-add-api              │
│ Last task: Add REST API endpoints (task-456)       │
│                                                     │
│ [Open in VS Code] [Delete Worktree]                │
└─────────────────────────────────────────────────────┘

[Create New Worktree]
```

### All Slots Locked Dialog

```
┌─ Cannot Start Agent ──────────────────────────────┐
│                                                    │
│ All worktree slots are currently in use.          │
│                                                    │
│ Active tasks:                                      │
│ • Task 1: Add user auth (main repo)               │
│ • Task 3: Build REST API (worktree-1)             │
│                                                    │
│ What would you like to do?                        │
│                                                    │
│ ○ Create new worktree                             │
│   Note: May take 30+ seconds for large repos      │
│                                                    │
│ ○ Wait for a slot to become available             │
│                                                    │
│ ○ Stop another task's agent                       │
│   [Select task to stop ▼]                         │
│                                                    │
│              [Cancel]  [Proceed]                  │
└────────────────────────────────────────────────────┘
```

---

## Services Architecture

### Core Services

**WorkspaceAllocationService**
- `allocate_for_task(task_id)` - Find/create slot with stickiness
- `release_slot(slot_id)` - Unlock slot when agent stops
- `create_and_lock_slot(task)` - Create new worktree and lock it
- `cleanup_stale_locks()` - Remove locks for inactive tasks

**TaskGitService**
- `create_task_branch(task)` - Create git branch for task
- `get_task_git_status(task_id)` - Query branch status (ahead/behind)
- `merge_task_branch(task_id)` - Merge to base branch
- `delete_task_branch(task_id)` - Delete branch after merge

**WorktreePoolService**
- `get_pool_status(codebase_id)` - Get all slots with status
- `create_worktree_slot(codebase_id, branch)` - Add slot to pool
- `delete_worktree_slot(slot_id)` - Remove slot from pool
- `reconcile_state(codebase_id)` - Sync DB with git reality

**CodebaseIntegration** (Enhanced)
- `create_branch(name, base)` - Create branch (don't checkout)
- `checkout_branch(name)` - Checkout existing branch
- `list_worktrees()` - Parse `git worktree list --porcelain`
- `create_worktree(path, branch)` - `git worktree add`
- `remove_worktree(path)` - `git worktree remove`
- `get_branch_comparison(branch, base)` - Ahead/behind/conflicts
- `merge_branch(source, target)` - Merge with conflict detection
- `get_current_branch()` - Get checked-out branch
- `get_status()` - Check for uncommitted changes

---

## Future Enhancements

### Phase 2: Optional Git Integration Features

**Per-codebase opt-in** for advanced features:

1. **Git Hooks Installation**
   - `pre-checkout` hook: Prevent branch switching when slot locked
   - Friendly error messages
   - User can override with `--no-verify`

2. **Lock File Creation**
   - Location: `.git/devboard.lock` (not in working tree)
   - Used by git hooks
   - Contains task info for user visibility

3. **Gitignore Management**
   - Optionally add `.devboard/` to `.gitignore`
   - For any DevBoard metadata in working tree

**Configuration UI**:
```
Codebase Settings → Git Integration
  ☐ Enable advanced git integration
    ☐ Install git hooks (prevent accidental branch switches)
    ☐ Update .gitignore (add .devboard/)
```

### Phase 3: Advanced Features

1. **Sparse Checkout**
   - Only checkout relevant subdirectories in worktrees
   - Massive performance improvement for monorepos
   - Example: Backend task only checks out `backend/` directory

2. **LLM Branch Naming**
   - Agent analyzes task title/description
   - Suggests semantic branch names
   - Follows repository conventions (detected from existing branches)

3. **Dependency Tracking**
   - Detect when Task B depends on Task A
   - Suggest creating Task B's branch from Task A's branch
   - Show merge order recommendations

4. **Conflict Detection**
   - Proactively detect when multiple tasks modify same files
   - Warn users before merge
   - Suggest merge order

5. **Branch Lifecycle Automation**
   - Auto-delete branch after successful merge (if configured)
   - Auto-cleanup stale branches (no activity for N days)
   - Protect important branches from deletion

---

## Success Metrics

**Usability**:
- Task-to-branch mapping is clear and intuitive
- Worktree allocation is transparent to user
- Parallel development "just works"

**Performance**:
- Minimal branch switching overhead
- Efficient worktree reuse (pool doesn't grow unbounded)
- Fast allocation decisions (<100ms)

**Reliability**:
- Stale locks detected and cleaned up
- State reconciliation handles external changes
- Graceful error handling when git operations fail

**Flexibility**:
- Works for single-task workflows (no worktrees needed)
- Scales to parallel workflows (dynamic worktree creation)
- User controls parallelism level

---

## Migration Path

### Phase 1: Core Implementation (MVP)

**Database**:
- Add git fields to Task model
- Create WorktreeSlot model
- Migration script

**Backend**:
- TaskGitService (branch creation, status, merge)
- WorkspaceAllocationService (slot allocation, locking)
- WorktreePoolService (pool management)
- Enhanced CodebaseIntegration (worktree operations)
- State reconciliation on startup

**Frontend**:
- Enhanced task creation form (branch configuration)
- Git status panel in task detail view
- Worktree pool status view
- "All slots locked" dialog

**APIs**:
- Task git status endpoint
- Worktree pool endpoints
- Workspace allocation endpoint
- Branch merge endpoint

### Phase 2: Polish & Optimization

- Stickiness algorithm refinement
- Performance monitoring
- Error handling improvements
- User settings for worktree behavior

### Phase 3: Optional Advanced Features

- Git hooks installation
- Lock file creation
- LLM branch naming
- Sparse checkout support

---

## Open Questions & Decisions

### Resolved

✅ **Lock by task or conversation?** → Task (branch is tied to task, not conversation)

✅ **Store base_branch?** → Yes (can't derive merge target from git alone)

✅ **Worktree location?** → Sibling directories (user-friendly, discoverable)

✅ **WorktreeSlot and WorktreeLock combined?** → Yes (single table simpler)

✅ **Lock file needed?** → No (future enhancement, only with git hooks)

✅ **Always require branch?** → Yes (every task has a branch when git enabled)

### To Be Determined

⏳ **Default auto-create worktrees setting?** → Prompt user, or always/never?

⏳ **Worktree cleanup strategy?** → Time-based (7 days) or LRU-based?

⏳ **Max pool size default?** → Unlimited, or cap at reasonable number (e.g., 5)?

⏳ **Branch naming default?** → Template-based or LLM-generated?

⏳ **Force unlock UI?** → Should users be able to force-unlock slots?

---

## Conclusion

This feature enables DevBoard to support both **sequential** (single-task) and **parallel** (multi-task) development workflows through intelligent git branch and worktree management.

**Key benefits**:
- ✅ Every task has a dedicated git branch
- ✅ Worktree pool enables true parallelism
- ✅ Task stickiness minimizes branch switching
- ✅ Automatic lock management prevents conflicts
- ✅ Scales from 1 to N concurrent tasks efficiently
- ✅ User-friendly (sibling directories, IDE integration)

**Implementation approach**: Start with core MVP (Phase 1), validate with users, then add advanced features based on feedback.
