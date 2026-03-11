// @vitest-environment node
import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '../uiStore'
import type { TabType } from '../uiStore'

describe('uiStore - visitedTabs tracking', () => {
  beforeEach(() => {
    // Reset store before each test
    const store = useUIStore.getState()
    store.tabs.forEach((tab) => store.closeTab(tab.id))
    useUIStore.setState({ visitedTabs: new Set() })
  })

  it('initializes with empty visitedTabs set', () => {
    const { visitedTabs } = useUIStore.getState()
    expect(visitedTabs).toBeInstanceOf(Set)
    expect(visitedTabs.size).toBe(0)
  })

  it('marks tab as visited when opening a new tab', () => {
    const { openTab } = useUIStore.getState()

    const tabId = openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    const { visitedTabs } = useUIStore.getState()
    expect(visitedTabs.has(tabId)).toBe(true)
  })

  it('marks tab as visited when switching to existing tab', () => {
    const { openTab, switchTab, visitedTabs, closeTab } = useUIStore.getState()

    // Open first tab
    const tab1Id = openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    // Open second tab
    const tab2Id = openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    // Clear visitedTabs to simulate page refresh
    useUIStore.setState({ visitedTabs: new Set() })
    expect(visitedTabs.size).toBe(0)

    // Switch to first tab
    switchTab(tab1Id)
    const updatedVisitedTabs = useUIStore.getState().visitedTabs
    expect(updatedVisitedTabs.has(tab1Id)).toBe(true)
    expect(updatedVisitedTabs.has(tab2Id)).toBe(false)

    // Switch to second tab
    switchTab(tab2Id)
    const finalVisitedTabs = useUIStore.getState().visitedTabs
    expect(finalVisitedTabs.has(tab1Id)).toBe(true)
    expect(finalVisitedTabs.has(tab2Id)).toBe(true)

    // Clean up
    closeTab(tab1Id)
    closeTab(tab2Id)
  })

  it('removes tab from visitedTabs when closing tab', () => {
    const { openTab, closeTab } = useUIStore.getState()

    const tabId = openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    let visitedTabs = useUIStore.getState().visitedTabs
    expect(visitedTabs.has(tabId)).toBe(true)

    closeTab(tabId)
    visitedTabs = useUIStore.getState().visitedTabs
    expect(visitedTabs.has(tabId)).toBe(false)
  })

  it('tracks multiple visited tabs independently', () => {
    const { openTab } = useUIStore.getState()

    const tab1Id = openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    const tab2Id = openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    const tab3Id = openTab({
      type: 'project' as TabType,
      entityId: 'project1',
      title: 'Project 1'
    })

    const { visitedTabs } = useUIStore.getState()
    expect(visitedTabs.has(tab1Id)).toBe(true)
    expect(visitedTabs.has(tab2Id)).toBe(true)
    expect(visitedTabs.has(tab3Id)).toBe(true)
    expect(visitedTabs.size).toBe(3)
  })

  it('marks tab as visited when opening existing tab by entity', () => {
    const { openTab, visitedTabs, closeTab } = useUIStore.getState()

    // Open first tab
    const tab1Id = openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    // Clear visitedTabs to simulate it being unmarked
    useUIStore.setState({ visitedTabs: new Set() })

    // Try to open same tab again (should switch to existing)
    const tab2Id = openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    // Should be the same tab ID
    expect(tab1Id).toBe(tab2Id)

    // Should be marked as visited
    const updatedVisitedTabs = useUIStore.getState().visitedTabs
    expect(updatedVisitedTabs.has(tab1Id)).toBe(true)

    // Clean up
    closeTab(tab1Id)
  })

  it('markTabVisited action adds tab to visitedTabs set', () => {
    const { openTab, markTabVisited, closeTab } = useUIStore.getState()

    const tabId = openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    // Clear visitedTabs
    useUIStore.setState({ visitedTabs: new Set() })
    let visitedTabs = useUIStore.getState().visitedTabs
    expect(visitedTabs.has(tabId)).toBe(false)

    // Mark as visited
    markTabVisited(tabId)
    visitedTabs = useUIStore.getState().visitedTabs
    expect(visitedTabs.has(tabId)).toBe(true)

    // Clean up
    closeTab(tabId)
  })

  it('maintains visitedTabs across tab switches', () => {
    const { openTab, switchTab } = useUIStore.getState()

    const tab1Id = openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    const tab2Id = openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    let visitedTabs = useUIStore.getState().visitedTabs
    // Both should be visited
    expect(visitedTabs.has(tab1Id)).toBe(true)
    expect(visitedTabs.has(tab2Id)).toBe(true)

    // Switch back to first tab
    switchTab(tab1Id)
    visitedTabs = useUIStore.getState().visitedTabs

    // Both should still be visited
    expect(visitedTabs.has(tab1Id)).toBe(true)
    expect(visitedTabs.has(tab2Id)).toBe(true)
  })
})
