// @vitest-environment node
import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '../uiStore'
import type { ViewType } from '../uiStore'

function resetStore() {
  useUIStore.setState({
    cachedViews: [],
    activeViewId: null,
    draftMessages: {},
    shouldPushHistory: false,
  })
}

describe('uiStore - view cache management', () => {
  beforeEach(resetStore)

  it('initializes with empty cachedViews', () => {
    const { cachedViews } = useUIStore.getState()
    expect(cachedViews).toEqual([])
  })

  it('creates a new view when navigating', () => {
    const { navigateTo } = useUIStore.getState()

    const viewId = navigateTo({
      type: 'home' as ViewType,
      entityId: 'main',
      title: 'Home'
    })

    const { cachedViews, activeViewId } = useUIStore.getState()
    expect(cachedViews).toHaveLength(1)
    expect(cachedViews[0].id).toBe(viewId)
    expect(activeViewId).toBe(viewId)
  })

  it('switches to existing view when navigating to same entity', () => {
    const { navigateTo } = useUIStore.getState()

    const view1Id = navigateTo({
      type: 'task' as ViewType,
      entityId: 'task1',
      title: 'Task 1'
    })

    const view2Id = navigateTo({
      type: 'task' as ViewType,
      entityId: 'task1',
      title: 'Task 1'
    })

    expect(view1Id).toBe(view2Id)
    expect(useUIStore.getState().cachedViews).toHaveLength(1)
  })

  it('switches active view with switchTab', () => {
    const { navigateTo, switchTab } = useUIStore.getState()

    const view1Id = navigateTo({ type: 'home', entityId: 'main', title: 'Home' })
    const view2Id = navigateTo({ type: 'task', entityId: 'task1', title: 'Task 1' })

    expect(useUIStore.getState().activeViewId).toBe(view2Id)

    switchTab(view1Id)
    expect(useUIStore.getState().activeViewId).toBe(view1Id)
  })

  it('removes view from cachedViews when evicting', () => {
    const { navigateTo, evictView } = useUIStore.getState()

    const viewId = navigateTo({ type: 'task', entityId: 'task1', title: 'Task 1' })
    expect(useUIStore.getState().cachedViews).toHaveLength(1)

    evictView(viewId)
    expect(useUIStore.getState().cachedViews).toHaveLength(0)
  })

  it('tracks multiple views independently', () => {
    const { navigateTo } = useUIStore.getState()

    navigateTo({ type: 'home', entityId: 'main', title: 'Home' })
    navigateTo({ type: 'task', entityId: 'task1', title: 'Task 1' })
    navigateTo({ type: 'project', entityId: 'project1', title: 'Project 1' })

    expect(useUIStore.getState().cachedViews).toHaveLength(3)
  })

  it('finds view by entity type and ID', () => {
    const { navigateTo, findViewByEntity } = useUIStore.getState()

    const viewId = navigateTo({ type: 'task', entityId: 'task1', title: 'Task 1' })

    expect(findViewByEntity('task', 'task1')?.id).toBe(viewId)
    expect(findViewByEntity('project', 'task1')).toBeUndefined()
  })

  it('updates view properties', () => {
    const { navigateTo, updateView } = useUIStore.getState()

    const viewId = navigateTo({ type: 'task', entityId: 'task1', title: 'Task 1' })
    updateView(viewId, { title: 'Updated Title' })

    expect(useUIStore.getState().cachedViews[0].title).toBe('Updated Title')
  })

  it('updates lastActivity on navigation to existing view', () => {
    const { navigateTo } = useUIStore.getState()

    navigateTo({ type: 'task', entityId: 'task1', title: 'Task 1' })
    const firstActivity = new Date(useUIStore.getState().cachedViews[0].lastActivity).getTime()

    // Navigate to something else, then back
    navigateTo({ type: 'home', entityId: 'main', title: 'Home' })
    navigateTo({ type: 'task', entityId: 'task1', title: 'Task 1' })

    const secondActivity = new Date(useUIStore.getState().cachedViews[0].lastActivity).getTime()
    expect(secondActivity).toBeGreaterThanOrEqual(firstActivity)
  })
})

describe('uiStore - LRU eviction', () => {
  beforeEach(resetStore)

  it('evicts LRU entry when cache exceeds max size', () => {
    const { navigateTo } = useUIStore.getState()

    // Fill cache to max (12 views)
    const viewIds: string[] = []
    for (let i = 0; i < 12; i++) {
      viewIds.push(navigateTo({ type: 'task', entityId: `task${i}`, title: `Task ${i}` }))
    }
    expect(useUIStore.getState().cachedViews).toHaveLength(12)

    // Adding one more should evict the oldest (task0, since all others were accessed more recently)
    navigateTo({ type: 'task', entityId: 'task99', title: 'Task 99' })

    const state = useUIStore.getState()
    expect(state.cachedViews).toHaveLength(12)
    // task0 should have been evicted (least recently used)
    expect(state.findViewByEntity('task', 'task0')).toBeUndefined()
    // task99 should exist
    expect(state.findViewByEntity('task', 'task99')).toBeDefined()
  })

  it('does not evict the active view', () => {
    const { navigateTo, switchTab } = useUIStore.getState()

    // Create 12 views
    const viewIds: string[] = []
    for (let i = 0; i < 12; i++) {
      viewIds.push(navigateTo({ type: 'task', entityId: `task${i}`, title: `Task ${i}` }))
    }

    // Switch back to the first view (task0), making it active and updating its lastActivity
    switchTab(viewIds[0])

    // Now add a new view — task1 should be evicted (oldest non-active), not task0
    navigateTo({ type: 'task', entityId: 'task99', title: 'Task 99' })

    const state = useUIStore.getState()
    // task0 is still the activeView, should NOT be evicted
    expect(state.findViewByEntity('task', 'task0')).toBeDefined()
    // task1 was the oldest non-active, should be evicted
    expect(state.findViewByEntity('task', 'task1')).toBeUndefined()
  })

  it('does not evict views with drafts', () => {
    const { navigateTo, saveDraftText, setHasDraft } = useUIStore.getState()

    // Create 12 views
    for (let i = 0; i < 12; i++) {
      navigateTo({ type: 'task', entityId: `task${i}`, title: `Task ${i}` })
    }

    // Set draft on task0 (the oldest view) — conversationId 0 is arbitrary here
    saveDraftText(0, 'Work in progress...')
    setHasDraft('task', 'task0', true)

    // Add a new view — task1 should be evicted (oldest without draft), not task0
    navigateTo({ type: 'task', entityId: 'task99', title: 'Task 99' })

    const state = useUIStore.getState()
    expect(state.findViewByEntity('task', 'task0')).toBeDefined()
    expect(state.findViewByEntity('task', 'task1')).toBeUndefined()
  })

  it('allows cache to exceed max when all entries have drafts', () => {
    const { navigateTo, setHasDraft } = useUIStore.getState()

    // Create 12 views all with drafts
    for (let i = 0; i < 12; i++) {
      navigateTo({ type: 'task', entityId: `task${i}`, title: `Task ${i}` })
      setHasDraft('task', `task${i}`, true)
    }

    // Add one more — cache should exceed max since all are draft-pinned
    navigateTo({ type: 'task', entityId: 'task99', title: 'Task 99' })

    expect(useUIStore.getState().cachedViews).toHaveLength(13)
  })
})

describe('uiStore - draft messages', () => {
  beforeEach(resetStore)

  it('sets and gets draft messages by conversationId', () => {
    const { saveDraftText, getDraftMessage } = useUIStore.getState()

    saveDraftText(42, 'Hello draft')
    expect(getDraftMessage(42)).toBe('Hello draft')
  })

  it('returns empty string for non-existent drafts', () => {
    const { getDraftMessage } = useUIStore.getState()
    expect(getDraftMessage(999)).toBe('')
  })

  it('clears draft messages by conversationId', () => {
    const { saveDraftText, clearDraftMessage, getDraftMessage } = useUIStore.getState()

    saveDraftText(42, 'Hello draft')
    expect(getDraftMessage(42)).toBe('Hello draft')

    clearDraftMessage(42, 'task', '1')
    expect(getDraftMessage(42)).toBe('')
  })

  it('draft keys are conversation-specific, not entity-specific', () => {
    const { saveDraftText, getDraftMessage } = useUIStore.getState()

    // Two different conversations belonging to the same entity
    saveDraftText(10, 'Draft for conversation 10')

    expect(getDraftMessage(10)).toBe('Draft for conversation 10')
    // Conversation 11 has no draft even though same entity
    expect(getDraftMessage(11)).toBe('')
  })

  it('sets hasDraft flag on cached view via setHasDraft', () => {
    const { navigateTo, setHasDraft } = useUIStore.getState()

    navigateTo({ type: 'task', entityId: '1', title: 'Task 1' })
    expect(useUIStore.getState().cachedViews[0].hasDraft).toBe(false)

    setHasDraft('task', '1', true)
    expect(useUIStore.getState().cachedViews[0].hasDraft).toBe(true)
  })

  it('clears hasDraft flag on cached view when clearDraftMessage is called', () => {
    const { navigateTo, setHasDraft, clearDraftMessage } = useUIStore.getState()

    navigateTo({ type: 'task', entityId: '1', title: 'Task 1' })
    setHasDraft('task', '1', true)
    expect(useUIStore.getState().cachedViews[0].hasDraft).toBe(true)

    clearDraftMessage(42, 'task', '1')
    expect(useUIStore.getState().cachedViews[0].hasDraft).toBe(false)
  })

  it('saveDraftText does not affect hasDraft flag', () => {
    const { navigateTo, saveDraftText } = useUIStore.getState()

    navigateTo({ type: 'task', entityId: '1', title: 'Task 1' })
    saveDraftText(42, 'draft text')
    expect(useUIStore.getState().cachedViews[0].hasDraft).toBe(false)
  })

  it('new view initializes with hasDraft false regardless of stored drafts', () => {
    const { navigateTo, saveDraftText, evictView } = useUIStore.getState()

    // Create view, save a draft for its conversation, then evict
    const viewId = navigateTo({ type: 'task', entityId: '1', title: 'Task 1' })
    saveDraftText(42, 'my draft')
    evictView(viewId)

    // Re-navigate: new view should start with hasDraft false
    // (the hook will set it correctly on mount)
    navigateTo({ type: 'task', entityId: '1', title: 'Task 1' })
    expect(useUIStore.getState().cachedViews[0].hasDraft).toBe(false)
  })

  it('draft text persists after view eviction and can be retrieved by conversationId', () => {
    const { navigateTo, saveDraftText, getDraftMessage, evictView } = useUIStore.getState()

    const viewId = navigateTo({ type: 'task', entityId: '1', title: 'Task 1' })
    saveDraftText(42, 'my draft')
    evictView(viewId)

    // Draft text is still accessible by conversationId even after view eviction
    expect(getDraftMessage(42)).toBe('my draft')
  })
})
