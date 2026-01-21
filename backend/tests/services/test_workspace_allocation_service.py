"""Tests for WorkspaceAllocationService."""

import datetime
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.events import SystemEvent, SystemEventType
from devboard.db.models import Codebase, Task, WorktreeSlot
from devboard.services.workspace_allocation_service import (
    AllSlotsLockedException,
    WorkspaceAllocationService,
)


@pytest.fixture
def mock_repos():
    """Create mock repositories."""
    worktree_slot_repo = MagicMock()
    task_repo = MagicMock()
    task_repo.db = MagicMock()  # Mock db for commit() calls
    conversation_repo = MagicMock()
    return worktree_slot_repo, task_repo, conversation_repo


@pytest.fixture
def service(mock_repos):
    """Create service instance with mocked repos."""
    worktree_slot_repo, task_repo, conversation_repo = mock_repos
    service = WorkspaceAllocationService(
        worktree_slot_repo=worktree_slot_repo,
        task_repo=task_repo,
        conversation_repo=conversation_repo,
    )
    # Mock TaskGitService.ensure_task_branch to avoid git operations in tests
    service.task_git_service.ensure_task_branch = AsyncMock(return_value="feature/test-branch")
    return service


@pytest.fixture
def sample_codebase():
    """Create a sample codebase."""
    codebase = MagicMock(spec=Codebase)
    codebase.id = 1
    codebase.local_path = "/projects/test-repo"
    codebase.name = "Test Repo"
    codebase.max_worktrees = None  # Default: unlimited worktrees
    return codebase


@pytest.fixture
def sample_task(sample_codebase):
    """Create a sample task."""
    task = MagicMock(spec=Task)
    task.id = 1
    task.branch_name = "feature/test-branch"
    task.base_branch = "main"
    task.codebase_id = 1
    task.codebase = sample_codebase
    task.title = "Test Task"
    return task


@pytest.fixture
def sample_slot():
    """Create a sample worktree slot (non-main repo)."""
    slot = MagicMock(spec=WorktreeSlot)
    slot.id = 1
    slot.path = "/projects/test-repo.worktree-1"
    slot.is_main_repo = False
    slot.locked_by_task_id = None
    slot.last_used_by_task_id = None
    slot.last_used_at = datetime.datetime.now(datetime.UTC)
    slot.get_current_branch = AsyncMock(return_value="main")
    return slot


@pytest.mark.asyncio
async def test_allocate_for_task_sticky_slot(service, mock_repos, sample_task, sample_codebase, sample_slot):
    """Test allocation with task stickiness (prefer previously used slot)."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Task previously used this slot
    sample_slot.last_used_by_task_id = sample_task.id
    sample_slot.locked = False  # Available
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot  # Return same slot after locking
    # Mock git dirty check (clean slot)
    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute (no branch checkout - that's caller's responsibility)
        result = await service.allocate_for_task(sample_task)

    # Verify: Returned the sticky slot
    assert result.id == sample_slot.id
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_branch_optimization(service, mock_repos, sample_task, sample_codebase, sample_slot):
    """Test allocation with branch optimization (slot already on base branch)."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: No sticky slot, but slot already on base branch
    sample_slot.locked = False  # Available
    sample_slot.last_used_by_task_id = 99  # Not this task
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot  # Return same slot after locking
    # Mock the slot's current branch to match task's base branch
    sample_slot.get_current_branch.return_value = sample_task.base_branch

    # Mock git dirty check (clean slot)
    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute - should use branch optimization
        result = await service.allocate_for_task(sample_task)

    # Verify: Used branch optimization
    assert result.id == sample_slot.id
    worktree_slot_repo.lock_slot.assert_called_once_with(sample_slot, sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_all_slots_locked(service, mock_repos, sample_task, sample_codebase):
    """Test allocation when all slots are locked."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: All slots are locked (empty available_slots)
    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.locked = True
    locked_slot.last_used_by_task = MagicMock()
    locked_slot.last_used_by_task.id = 2
    locked_slot.last_used_by_task.title = "Other Task"
    locked_slot.path = "/projects/test-repo"

    worktree_slot_repo.get_by_codebase.return_value = [locked_slot]  # Only locked slots
    # Execute and verify exception
    with pytest.raises(AllSlotsLockedException):
        await service.allocate_for_task(sample_task)


@pytest.mark.asyncio
async def test_cleanup_stale_locks(service, mock_repos, sample_codebase):
    """Test cleanup of stale locks based on last_used_at age."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Locked slot from 2 hours ago (older than 1h threshold)
    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.id = 1
    locked_slot.last_used_by_task_id = 1
    locked_slot.last_used_at = datetime.datetime.now(datetime.UTC) - timedelta(hours=2)

    worktree_slot_repo.get_all_locked.return_value = [locked_slot]

    # Execute
    released_count = await service.cleanup_stale_locks(sample_codebase.id)

    # Verify: Lock was released (>1h age threshold)
    assert released_count == 1
    worktree_slot_repo.unlock_slot.assert_called_once_with(locked_slot)


@pytest.mark.asyncio
async def test_cleanup_stale_locks_does_not_release_recent(service, mock_repos, sample_codebase):
    """Test that locks within the 1h threshold are not released."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Recently locked slot (30 minutes ago, within 1h threshold)
    recent_slot = MagicMock(spec=WorktreeSlot)
    recent_slot.id = 1
    recent_slot.last_used_by_task_id = 1
    recent_slot.last_used_at = datetime.datetime.now(datetime.UTC) - timedelta(minutes=30)

    worktree_slot_repo.get_all_locked.return_value = [recent_slot]

    # Execute
    released_count = await service.cleanup_stale_locks(sample_codebase.id)

    # Verify: Lock was NOT released (within 1h threshold)
    assert released_count == 0
    worktree_slot_repo.unlock_slot.assert_not_called()


def test_bootstrap_main_repo_slot(service, mock_repos, sample_codebase):
    """Test bootstrapping main repo slot when none exists."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: No existing slots
    worktree_slot_repo.find_one.return_value = None  # No slot found
    worktree_slot_repo.get_by_path.return_value = None  # No slot at main repo path

    # Mock slot creation
    new_slot = MagicMock(spec=WorktreeSlot)
    new_slot.id = 1
    new_slot.path = sample_codebase.local_path
    new_slot.is_main_repo = True
    worktree_slot_repo.create.return_value = new_slot

    # Execute (not async)
    service.bootstrap_main_repo_slot(sample_codebase)

    # Verify: Created main repo slot
    worktree_slot_repo.create.assert_called_once()


def test_release_slot(service, mock_repos):
    """Test releasing a slot."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Mock slot
    slot = MagicMock(spec=WorktreeSlot)
    slot.id = 1

    # Execute (not async) - now takes WorktreeSlot instance
    service.release_slot(slot)

    # Verify: Unlocked the slot
    worktree_slot_repo.unlock_slot.assert_called_once_with(slot)


@pytest.mark.asyncio
async def test_run_task_agent_in_workspace_yields_system_events_existing_slot(
    service, mock_repos, sample_task, sample_slot
):
    """Test that run_task_agent_in_workspace yields appropriate SystemEvents when allocating existing slot."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Available slot
    sample_slot.locked = False
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot

    # Mock git operations and worktree validation
    with (
        patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git,
        patch.object(service, "_check_worktree_valid", return_value=True),
    ):
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)
        mock_git.return_value.checkout_branch = AsyncMock()
        mock_git.return_value.get_current_branch = AsyncMock(return_value="main")

        # Mock agent stream that yields one message
        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        # Execute and collect events
        events = []
        async for event in service.run_task_agent_in_workspace(
            task=sample_task,
            agent_stream=mock_agent_stream(),
        ):
            events.append(event)

    # Verify: Should have yielded WORKSPACE_ALLOCATE and WORKSPACE_BRANCH_CHECKOUT SystemEvents
    system_events = [e for e in events if isinstance(e, SystemEvent)]
    assert len(system_events) == 2

    # Verify first event: WORKSPACE_ALLOCATE
    assert system_events[0].type == SystemEventType.WORKSPACE_ALLOCATE
    assert system_events[0].data["task_id"] == sample_task.id
    assert system_events[0].data["slot_id"] == sample_slot.id

    # Verify second event: WORKSPACE_BRANCH_CHECKOUT
    assert system_events[1].type == SystemEventType.WORKSPACE_BRANCH_CHECKOUT
    assert system_events[1].data["task_id"] == sample_task.id
    assert system_events[1].data["branch"] == sample_task.branch_name

    # Verify slot was released
    worktree_slot_repo.unlock_slot.assert_called_once_with(sample_slot)


@pytest.mark.asyncio
async def test_run_task_agent_in_workspace_no_allocate_event_for_sticky_slot(
    service, mock_repos, sample_task, sample_slot
):
    """Test that WORKSPACE_ALLOCATE is NOT emitted when task reuses its sticky slot."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: Slot is task's sticky slot (last_used_by_task_id matches task.id)
    sample_slot.locked = False
    sample_slot.last_used_by_task_id = sample_task.id
    worktree_slot_repo.get_by_codebase.return_value = [sample_slot]
    worktree_slot_repo.lock_slot.return_value = sample_slot
    # Mock that this task previously used this slot
    worktree_slot_repo.get_last_used_slot_for_task.return_value = sample_slot

    # Mock git operations and worktree validation
    with (
        patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git,
        patch.object(service, "_check_worktree_valid", return_value=True),
        patch.object(service, "checkout_branch_in_slot", new_callable=AsyncMock) as mock_checkout,
    ):
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)
        mock_checkout.return_value = True  # Checkout was performed

        # Mock agent stream that yields one message
        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        # Execute and collect events
        events = []
        async for event in service.run_task_agent_in_workspace(
            task=sample_task,
            agent_stream=mock_agent_stream(),
        ):
            events.append(event)

    # Verify: Should NOT have yielded WORKSPACE_ALLOCATE (sticky slot reuse)
    # Only WORKSPACE_BRANCH_CHECKOUT should be emitted
    system_events = [e for e in events if isinstance(e, SystemEvent)]
    assert len(system_events) == 1

    # Verify only event: WORKSPACE_BRANCH_CHECKOUT
    assert system_events[0].type == SystemEventType.WORKSPACE_BRANCH_CHECKOUT
    assert system_events[0].data["task_id"] == sample_task.id
    assert system_events[0].data["branch"] == sample_task.branch_name


@pytest.mark.asyncio
async def test_run_task_agent_in_workspace_yields_workspace_create_event(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that run_task_agent_in_workspace yields WORKSPACE_CREATE when creating new worktree."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: All slots locked (force creation of new slot)
    locked_slot = MagicMock(spec=WorktreeSlot)
    locked_slot.locked = True
    worktree_slot_repo.get_by_codebase.return_value = [locked_slot]

    # Mock slot creation
    new_slot = MagicMock(spec=WorktreeSlot)
    new_slot.id = 2
    new_slot.path = "/projects/test-repo.worktree-1"
    new_slot.is_main_repo = False
    new_slot.locked = False
    worktree_slot_repo.create.return_value = new_slot
    worktree_slot_repo.lock_slot.return_value = new_slot

    # Mock main repo slot bootstrap
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 0
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    worktree_slot_repo.get_by_path.return_value = main_slot

    # Mock git operations
    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git:
        mock_git.return_value.create_worktree = AsyncMock()
        mock_git.return_value.checkout_branch = AsyncMock()
        mock_git.return_value.get_current_branch = AsyncMock(return_value="main")

        # Mock agent stream that yields one message
        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        # Execute and collect events
        events = []
        async for event in service.run_task_agent_in_workspace(
            task=sample_task,
            agent_stream=mock_agent_stream(),
        ):
            events.append(event)

    # Verify: Should have yielded WORKSPACE_CREATE (twice) and WORKSPACE_BRANCH_CHECKOUT
    # Note: WORKSPACE_ALLOCATE is not emitted after WORKSPACE_CREATE (creation implies allocation)
    system_events = [e for e in events if isinstance(e, SystemEvent)]
    assert len(system_events) == 3

    # Verify first event: WORKSPACE_CREATE (before creating slot)
    assert system_events[0].type == SystemEventType.WORKSPACE_CREATE
    assert system_events[0].data["task_id"] == sample_task.id

    # Verify second event: WORKSPACE_CREATE (worktree validation failed, recreating)
    assert system_events[1].type == SystemEventType.WORKSPACE_CREATE
    assert system_events[1].data["task_id"] == sample_task.id
    assert system_events[1].data["slot_id"] == new_slot.id

    # Verify third event: WORKSPACE_BRANCH_CHECKOUT
    assert system_events[2].type == SystemEventType.WORKSPACE_BRANCH_CHECKOUT
    assert system_events[2].data["task_id"] == sample_task.id
    assert system_events[2].data["branch"] == sample_task.branch_name

    # Verify worktree was created twice (once during slot creation, once during validation/recreation)
    assert mock_git.return_value.create_worktree.call_count == 2

    # Verify slot was released
    worktree_slot_repo.unlock_slot.assert_called_once_with(new_slot)


@pytest.mark.asyncio
async def test_allocate_for_task_bootstraps_main_repo_when_max_worktrees_zero(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that allocate_for_task bootstraps main repo slot when max_worktrees=0."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: max_worktrees=0 (main repo only mode)
    sample_codebase.max_worktrees = 0
    sample_task.codebase = sample_codebase

    # Setup: No existing slots initially
    worktree_slot_repo.get_by_path.return_value = None

    # Setup: Mock bootstrap to create main repo slot
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 1
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = False
    main_slot.last_used_by_task_id = None
    main_slot.last_used_at = datetime.datetime.now(datetime.UTC)
    main_slot.get_current_branch = AsyncMock(return_value="main")
    worktree_slot_repo.create.return_value = main_slot

    # After bootstrap, get_by_codebase returns the main slot
    worktree_slot_repo.get_by_codebase.return_value = [main_slot]
    worktree_slot_repo.lock_slot.return_value = main_slot

    # Mock git operations
    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute
        result = await service.allocate_for_task(sample_task)

    # Verify: bootstrap_main_repo_slot was called (via create)
    worktree_slot_repo.create.assert_called_once()
    call_kwargs = worktree_slot_repo.create.call_args[1]
    assert call_kwargs["is_main_repo"] is True
    assert call_kwargs["path"] == sample_codebase.local_path

    # Verify: Main slot was locked
    worktree_slot_repo.lock_slot.assert_called_once_with(main_slot, sample_task)
    assert result.id == main_slot.id


@pytest.mark.asyncio
async def test_run_task_agent_yields_stream_error_when_all_slots_locked(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that run_task_agent_in_workspace yields STREAM_ERROR when max slots reached."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: max_worktrees=0 (main repo only mode)
    sample_codebase.max_worktrees = 0
    sample_task.codebase = sample_codebase

    # Setup: Main repo slot exists but is locked
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 1
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = True  # Already locked by another task
    main_slot.last_used_by_task_id = 999  # Different task
    worktree_slot_repo.get_by_codebase.return_value = [main_slot]
    worktree_slot_repo.get_by_path.return_value = main_slot  # bootstrap finds existing

    # Mock git operations
    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Mock agent stream (should never be reached)
        async def mock_agent_stream():
            yield MagicMock(event_type="message")

        # Execute and collect events
        events = []
        async for event in service.run_task_agent_in_workspace(
            task=sample_task,
            agent_stream=mock_agent_stream(),
        ):
            events.append(event)

    # Verify: Should have yielded STREAM_ERROR event
    assert len(events) == 1
    error_event = events[0]
    assert isinstance(error_event, SystemEvent)
    assert error_event.type == SystemEventType.STREAM_ERROR
    assert error_event.data["error_code"] == "SLOTS_EXHAUSTED"
    assert "workspace slots available" in error_event.data["message"]

    # Verify: Slot was NOT released (never allocated)
    worktree_slot_repo.unlock_slot.assert_not_called()


# --- TaskGitService tests ---


@pytest.fixture
def task_git_service(mock_repos):
    """Create TaskGitService instance with mocked repos."""
    from devboard.services.task_git_service import TaskGitService

    worktree_slot_repo, task_repo, _ = mock_repos
    return TaskGitService(
        task_repo=task_repo,
        worktree_slot_repo=worktree_slot_repo,
    )


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_stashes_uncommitted_changes(service, mock_repos, sample_task, sample_slot):
    """Test that uncommitted changes from worktree are applied to main repo."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree - returns stash SHA from worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path="/projects/test-repo.worktree-1",
            stash_sha="abc123stashsha",
        )

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: release_branch_from_worktree was called
        main_git.release_branch_from_worktree.assert_called_once_with(sample_task.branch_name)

        # Verify: Branch checked out in main repo
        main_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: Stash applied in main repo
        main_git.stash_apply.assert_called_once_with("abc123stashsha")

        # Verify: Slot is assigned (not locked) to the task
        worktree_slot_repo.assign_slot.assert_called_once_with(main_slot, sample_task)
        worktree_slot_repo.lock_slot.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_no_stash_when_no_changes(service, mock_repos, sample_task, sample_slot):
    """Test that no stash is applied when worktree has no uncommitted changes."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree - no stash SHA (no uncommitted changes)
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path="/projects/test-repo.worktree-1",
            stash_sha=None,  # No uncommitted changes
        )

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: No stash applied (stash_sha was None)
        main_git.stash_apply.assert_not_called()

        # Verify: Branch still checked out
        main_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: Slot is assigned (not locked) to the task
        worktree_slot_repo.assign_slot.assert_called_once_with(main_slot, sample_task)
        worktree_slot_repo.lock_slot.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_task_branch_with_uncommitted_changes(task_git_service, mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch stashes changes, rebases, and restores stash."""
    from devboard.services.task_git_service import RebaseResult

    worktree_slot_repo, _, _ = mock_repos

    # Setup: Task has a worktree slot
    worktree_slot_repo.get_last_used_slot_for_task.return_value = sample_slot

    with patch("devboard.services.task_git_service.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # Has uncommitted changes
        mock_git.has_uncommitted_changes.return_value = True
        mock_git.stash_push.return_value = "abc123stashsha"
        mock_git.rebase_onto.return_value = "newhead456"

        # Execute
        result = await task_git_service.rebase_task_branch(sample_task)

        # Verify result
        assert isinstance(result, RebaseResult)
        assert result.new_head == "newhead456"
        assert result.slot_path == sample_slot.path
        assert result.had_uncommitted_changes is True
        assert result.uncommitted_changes_restored is True
        assert result.has_stash_conflicts is False

        # Verify stash flow (stash_push cleans working tree automatically)
        mock_git.has_uncommitted_changes.assert_called_once()
        mock_git.stash_push.assert_called_once_with(include_untracked=True)
        mock_git.fetch.assert_called_once()
        mock_git.rebase_onto.assert_called_once_with(sample_task.base_branch)
        mock_git.stash_apply.assert_called_once_with("abc123stashsha")


@pytest.mark.asyncio
async def test_rebase_task_branch_without_uncommitted_changes(task_git_service, mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch without uncommitted changes skips stash operations."""
    from devboard.services.task_git_service import RebaseResult

    worktree_slot_repo, _, _ = mock_repos
    worktree_slot_repo.get_last_used_slot_for_task.return_value = sample_slot

    with patch("devboard.services.task_git_service.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # No uncommitted changes
        mock_git.has_uncommitted_changes.return_value = False
        mock_git.rebase_onto.return_value = "newhead789"

        # Execute
        result = await task_git_service.rebase_task_branch(sample_task)

        # Verify result
        assert isinstance(result, RebaseResult)
        assert result.new_head == "newhead789"
        assert result.had_uncommitted_changes is False
        assert result.uncommitted_changes_restored is False
        assert result.has_stash_conflicts is False

        # Verify no stash operations when nothing to stash
        mock_git.stash_push.assert_not_called()
        mock_git.stash_apply.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_task_branch_conflict_restores_stash(task_git_service, mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch restores stash before raising RebaseConflictError."""
    from devboard.integrations.shell import RebaseConflictError

    worktree_slot_repo, _, _ = mock_repos
    worktree_slot_repo.get_last_used_slot_for_task.return_value = sample_slot

    with patch("devboard.services.task_git_service.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # Has uncommitted changes
        mock_git.has_uncommitted_changes.return_value = True
        mock_git.stash_push.return_value = "abc123stashsha"
        mock_git.rebase_onto.side_effect = RebaseConflictError("Rebase conflict on file.txt")

        # Execute and verify exception is raised
        with pytest.raises(RebaseConflictError):
            await task_git_service.rebase_task_branch(sample_task)

        # Verify stash was created before rebase
        mock_git.stash_push.assert_called_once_with(include_untracked=True)

        # Verify stash was restored after conflict
        mock_git.stash_apply.assert_called_once_with("abc123stashsha")


@pytest.mark.asyncio
async def test_rebase_task_branch_stash_apply_conflict(task_git_service, mock_repos, sample_task, sample_slot):
    """Test rebase_task_branch handles stash apply conflicts by storing pending stash."""
    from devboard.integrations.shell import ShellCommandExecutionError
    from devboard.services.task_git_service import RebaseResult

    worktree_slot_repo, _, _ = mock_repos
    worktree_slot_repo.get_last_used_slot_for_task.return_value = sample_slot

    with patch("devboard.services.task_git_service.GitRepoIntegration") as mock_git_class:
        mock_git = AsyncMock()
        mock_git_class.return_value = mock_git

        # Has uncommitted changes
        mock_git.has_uncommitted_changes.return_value = True
        mock_git.stash_push.return_value = "abc123stashsha"
        mock_git.rebase_onto.return_value = "newhead456"
        # Stash apply fails with conflict
        mock_git.stash_apply.side_effect = ShellCommandExecutionError("error: could not apply stash")

        # Execute
        result = await task_git_service.rebase_task_branch(sample_task)

        # Verify result has stash conflicts flag
        assert isinstance(result, RebaseResult)
        assert result.new_head == "newhead456"
        assert result.had_uncommitted_changes is True
        assert result.uncommitted_changes_restored is False
        assert result.has_stash_conflicts is True

        # Verify stash_push was called (cleans working tree automatically)
        mock_git.stash_push.assert_called_once_with(include_untracked=True)
        # Stash store is no longer called - files left in conflicted state
        mock_git.stash_store.assert_not_called()


@pytest.mark.asyncio
async def test_rebase_task_branch_no_branch_name_raises_error(task_git_service, mock_repos, sample_task):
    """Test rebase_task_branch raises ValueError when task has no branch name."""
    sample_task.branch_name = None

    with pytest.raises(ValueError, match="has no branch name configured"):
        await task_git_service.rebase_task_branch(sample_task)


@pytest.mark.asyncio
async def test_allocate_for_task_prefers_most_recent_sticky_slot(service, mock_repos, sample_task, sample_codebase):
    """Test that when multiple slots have same last_used_by_task_id, the most recent is preferred.

    This scenario occurs when a task is checked out from a worktree to main repo:
    - Both slots have last_used_by_task_id set to the task
    - The main repo has a more recent last_used_at (from checkout)
    - Allocation should pick the main repo (most recent), not the worktree
    """
    worktree_slot_repo, task_repo = mock_repos

    now = datetime.datetime.now(datetime.UTC)

    # Setup: Worktree slot - older last_used_at
    worktree_slot = MagicMock(spec=WorktreeSlot)
    worktree_slot.id = 1
    worktree_slot.path = "/projects/test-repo.worktree-1"
    worktree_slot.is_main_repo = False
    worktree_slot.locked = False
    worktree_slot.last_used_by_task_id = sample_task.id  # Same task
    worktree_slot.last_used_at = now - timedelta(hours=1)  # 1 hour ago
    worktree_slot.get_current_branch = AsyncMock(return_value="some-other-branch")

    # Setup: Main repo slot - more recent last_used_at (task was checked out here)
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 2
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = False
    main_slot.last_used_by_task_id = sample_task.id  # Same task
    main_slot.last_used_at = now  # Just now (more recent)
    main_slot.get_current_branch = AsyncMock(return_value=sample_task.branch_name)  # Branch matches

    # Return both slots (order doesn't matter since we sort by last_used_at)
    worktree_slot_repo.get_by_codebase.return_value = [worktree_slot, main_slot]
    worktree_slot_repo.lock_slot.return_value = main_slot

    # Mock git operations
    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute
        result = await service.allocate_for_task(sample_task)

    # Verify: Main slot (most recent) was selected, not worktree slot
    assert result.id == main_slot.id
    worktree_slot_repo.lock_slot.assert_called_once_with(main_slot, sample_task)


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_rolls_back_on_checkout_failure(service, mock_repos, sample_task, sample_slot):
    """Test that worktree is rolled back if checkout in main repo fails."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        worktree_git = AsyncMock()

        worktree_path = "/projects/test-repo.worktree-1"

        def create_git(path):
            if path == sample_task.codebase.local_path:
                return main_git
            return worktree_git

        mock_git_class.side_effect = create_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False
        # But checkout fails
        main_git.checkout_branch.side_effect = Exception("Checkout failed")

        # Mock release_branch_from_worktree - returns stash SHA
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path=worktree_path,
            stash_sha="abc123stashsha",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Checkout failed"):
            await service.checkout_task_to_main_repo(sample_task)

        # Verify: ROLLBACK - Branch was checked back out in worktree
        worktree_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: ROLLBACK - Stash was applied back to worktree
        worktree_git.stash_apply.assert_called_once_with("abc123stashsha")

        # Verify: Slot was NOT assigned (operation failed)
        worktree_slot_repo.assign_slot.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_rolls_back_on_stash_apply_failure(
    service, mock_repos, sample_task, sample_slot
):
    """Test that worktree is rolled back if stash apply in main repo fails."""
    worktree_slot_repo, _, _ = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git_class:
        main_git = AsyncMock()
        worktree_git = AsyncMock()

        worktree_path = "/projects/test-repo.worktree-1"

        def create_git(path):
            if path == sample_task.codebase.local_path:
                return main_git
            return worktree_git

        mock_git_class.side_effect = create_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False
        # Checkout succeeds but stash apply fails
        main_git.stash_apply.side_effect = Exception("Stash apply failed")

        # Mock release_branch_from_worktree - returns stash SHA
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path=worktree_path,
            stash_sha="abc123stashsha",
        )

        # Execute and verify exception is raised
        with pytest.raises(Exception, match="Stash apply failed"):
            await service.checkout_task_to_main_repo(sample_task)

        # Verify: Main repo checkout was attempted
        main_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: ROLLBACK - Branch was checked back out in worktree
        worktree_git.checkout_branch.assert_called_once_with(sample_task.branch_name)

        # Verify: ROLLBACK - Stash was applied back to worktree
        worktree_git.stash_apply.assert_called_once_with("abc123stashsha")

        # Verify: Slot was NOT assigned (operation failed)
        worktree_slot_repo.assign_slot.assert_not_called()


@pytest.mark.asyncio
async def test_allocate_uses_main_repo_assigned_but_not_locked_by_same_task(
    service, mock_repos, sample_task, sample_codebase
):
    """Test that allocate_for_task uses main repo slot assigned to same task (sticky slot)."""
    worktree_slot_repo, task_repo, _ = mock_repos

    # Setup: max_worktrees > 0 (normal mode, main repo excluded from automatic allocation)
    sample_codebase.max_worktrees = 2
    sample_task.codebase = sample_codebase

    # Setup: Main repo slot exists, assigned to this task but NOT locked
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.id = 1
    main_slot.path = sample_codebase.local_path
    main_slot.is_main_repo = True
    main_slot.locked = False  # Not locked
    main_slot.last_used_by_task_id = sample_task.id  # But assigned to this task
    main_slot.last_used_at = datetime.datetime.now(datetime.UTC)
    main_slot.get_current_branch = AsyncMock(return_value=sample_task.branch_name)

    worktree_slot_repo.get_by_codebase.return_value = [main_slot]
    worktree_slot_repo.lock_slot.return_value = main_slot

    # Mock git operations
    with patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git:
        mock_git.return_value.has_uncommitted_changes = AsyncMock(return_value=False)

        # Execute
        result = await service.allocate_for_task(sample_task)

    # Verify: Main slot was used (sticky slot with matching branch)
    assert result.id == main_slot.id
    worktree_slot_repo.lock_slot.assert_called_once_with(main_slot, sample_task)


# =============================================================================
# Session Migration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_migrates_claude_session(service, mock_repos, sample_task, sample_slot):
    """Test that Claude Code session is migrated when moving task from worktree to main repo."""
    worktree_slot_repo, _, conversation_repo = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    # Setup: Task has active Claude Code conversation
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = "test-session-123"
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with (
        patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git_class,
        patch("devboard.services.workspace_allocation_service.ClaudeCodeSessionService") as mock_session_service_class,
    ):
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        # Main repo is clean
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree - returns result indicating branch was in worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(
            worktree_path="/projects/test-repo.worktree-1",
            stash_sha=None,
        )

        # Mock session service
        mock_session_service = AsyncMock()
        mock_session_service_class.return_value = mock_session_service

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: Session was migrated (without old_working_dir - it's auto-detected)
        mock_session_service.migrate_session_to_directory.assert_called_once_with(
            session_id="test-session-123",
            new_working_dir=sample_task.codebase.local_path,
        )


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_skips_migration_for_internal_engine(
    service, mock_repos, sample_task, sample_slot
):
    """Test that session migration is skipped when task uses INTERNAL engine."""
    worktree_slot_repo, _, conversation_repo = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    # Setup: Task has active INTERNAL conversation (not Claude Code)
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.INTERNAL
    mock_conversation.external_session_id = None
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with (
        patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git_class,
        patch("devboard.services.workspace_allocation_service.ClaudeCodeSessionService") as mock_session_service_class,
    ):
        main_git = AsyncMock()
        mock_git_class.return_value = main_git

        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(None, None)

        # Execute
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: Session service was NOT called (INTERNAL engine)
        mock_session_service_class.assert_not_called()


@pytest.mark.asyncio
async def test_checkout_task_to_main_repo_handles_no_session_file(service, mock_repos, sample_task):
    """Test that checkout handles gracefully when no session file exists."""
    worktree_slot_repo, _, conversation_repo = mock_repos

    # Setup: Main slot exists
    main_slot = MagicMock(spec=WorktreeSlot)
    main_slot.is_main_repo = True
    worktree_slot_repo.get_main_slot_for_codebase.return_value = main_slot

    # Setup: Task has active Claude Code conversation
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = "test-session-123"
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with (
        patch("devboard.services.workspace_allocation_service.GitRepoIntegration") as mock_git_class,
        patch("devboard.services.workspace_allocation_service.ClaudeCodeSessionService") as mock_session_service_class,
    ):
        main_git = AsyncMock()
        mock_git_class.return_value = main_git
        main_git.has_uncommitted_changes.return_value = False

        # Mock release_branch_from_worktree
        from devboard.integrations.types import BranchReleaseResult

        main_git.release_branch_from_worktree.return_value = BranchReleaseResult(None, None)

        # Mock session service to raise FileNotFoundError (no session file)
        mock_session_service = AsyncMock()
        mock_session_service.migrate_session_to_directory.side_effect = FileNotFoundError("Session not found")
        mock_session_service_class.return_value = mock_session_service

        # Execute - should not raise
        await service.checkout_task_to_main_repo(sample_task)

        # Verify: Session migration was attempted but handled gracefully
        mock_session_service.migrate_session_to_directory.assert_called_once()


@pytest.mark.asyncio
async def test_migrate_claude_session_if_needed_skips_when_no_external_session_id(service, mock_repos, sample_task):
    """Test that session migration is skipped when conversation has no external_session_id."""
    _, _, conversation_repo = mock_repos

    # Setup: Task has Claude Code conversation but no external_session_id
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = None  # No session ID
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with patch("devboard.services.workspace_allocation_service.ClaudeCodeSessionService") as mock_session_service_class:
        # Execute
        await service._migrate_claude_session_if_needed(
            task=sample_task,
            new_working_dir="/new/path",
        )

        # Verify: Session service was NOT instantiated
        mock_session_service_class.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_claude_session_if_needed_skips_when_no_active_conversation(service, mock_repos, sample_task):
    """Test that session migration is skipped when task has no active conversation."""
    _, _, conversation_repo = mock_repos

    # Setup: No active conversation
    conversation_repo.get_active_conversation_for_entity.return_value = None

    with patch("devboard.services.workspace_allocation_service.ClaudeCodeSessionService") as mock_session_service_class:
        # Execute
        await service._migrate_claude_session_if_needed(
            task=sample_task,
            new_working_dir="/new/path",
        )

        # Verify: Session service was NOT instantiated
        mock_session_service_class.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_claude_session_if_needed_handles_file_not_found(service, mock_repos, sample_task):
    """Test that session migration handles FileNotFoundError gracefully."""
    _, _, conversation_repo = mock_repos

    # Setup: Task has Claude Code conversation
    mock_conversation = MagicMock()
    mock_conversation.engine = AgentEngine.CLAUDE_CODE
    mock_conversation.external_session_id = "test-session-123"
    conversation_repo.get_active_conversation_for_entity.return_value = mock_conversation

    with patch("devboard.services.workspace_allocation_service.ClaudeCodeSessionService") as mock_session_service_class:
        mock_session_service = AsyncMock()
        mock_session_service.migrate_session_to_directory.side_effect = FileNotFoundError("Session not found")
        mock_session_service_class.return_value = mock_session_service

        # Execute - should not raise
        await service._migrate_claude_session_if_needed(
            task=sample_task,
            new_working_dir="/new/path",
        )

        # Verify: Session migration was attempted
        mock_session_service.migrate_session_to_directory.assert_called_once()
