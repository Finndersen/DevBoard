import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TabContentContainer from '../TabContentContainer'
import { useUIStore } from '../../../stores/uiStore'
import type { TabType } from '../../../stores/uiStore'

// Mock the view components
vi.mock('../../../views/Home', () => ({
  default: () => <div data-testid="home-view">Home View</div>
}))

vi.mock('../../../views/TaskDetail', () => ({
  default: ({ id }: { id: string }) => <div data-testid={`task-view-${id}`}>Task Detail {id}</div>
}))

vi.mock('../../../views/ProjectDetail', () => ({
  default: ({ id }: { id: string }) => <div data-testid={`project-view-${id}`}>Project Detail {id}</div>
}))

vi.mock('../../../views/CodebaseDetail', () => ({
  default: ({ id }: { id: string }) => <div data-testid={`codebase-view-${id}`}>Codebase Detail {id}</div>
}))

vi.mock('../../../views/Settings', () => ({
  default: () => <div data-testid="settings-view">Settings View</div>
}))

describe('TabContentContainer - Lazy Mounting', () => {
  beforeEach(() => {
    // Reset store before each test
    const store = useUIStore.getState()
    store.tabs.forEach((tab) => store.closeTab(tab.id))
    useUIStore.setState({ visitedTabs: new Set(), activeTabId: null })
  })

  const renderWithRouter = () => {
    return render(
      <MemoryRouter>
        <TabContentContainer />
      </MemoryRouter>
    )
  }

  it('shows loading state when no tabs are open', () => {
    const { container } = renderWithRouter()

    // Should show loading spinner
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('only renders the active tab on initial mount', () => {
    const { openTab } = useUIStore.getState()

    // Open three tabs
    openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    const tab2Id = openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    openTab({
      type: 'project' as TabType,
      entityId: 'project1',
      title: 'Project 1'
    })

    // Clear visitedTabs to simulate fresh page load
    useUIStore.setState({ visitedTabs: new Set(), activeTabId: tab2Id })

    const { queryByTestId } = renderWithRouter()

    // Only the active tab (task1) should be rendered
    expect(queryByTestId('home-view')).not.toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).toBeInTheDocument()
    expect(queryByTestId('project-view-project1')).not.toBeInTheDocument()
  })

  it('renders previously visited tabs when they exist in visitedTabs', () => {
    const { openTab } = useUIStore.getState()

    // Open three tabs
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

    // Simulate that tab1 and tab3 have been visited, but clear activeTabId
    useUIStore.setState({
      visitedTabs: new Set([tab1Id, tab3Id]),
      activeTabId: tab2Id
    })

    const { queryByTestId } = renderWithRouter()

    // Active tab and visited tabs should be rendered
    expect(queryByTestId('home-view')).toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).toBeInTheDocument()
    expect(queryByTestId('project-view-project1')).toBeInTheDocument()
  })

  it('does not render unvisited, inactive tabs', () => {
    const { openTab } = useUIStore.getState()

    // Open three tabs
    const tab1Id = openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    openTab({
      type: 'project' as TabType,
      entityId: 'project1',
      title: 'Project 1'
    })

    // Only tab1 is visited and active
    useUIStore.setState({
      visitedTabs: new Set([tab1Id]),
      activeTabId: tab1Id
    })

    const { queryByTestId } = renderWithRouter()

    // Only the visited tab should be rendered
    expect(queryByTestId('home-view')).toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).not.toBeInTheDocument()
    expect(queryByTestId('project-view-project1')).not.toBeInTheDocument()
  })

  it('applies correct visibility styles to active vs inactive tabs', () => {
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

    // Both tabs are visited, tab2 is active
    useUIStore.setState({
      visitedTabs: new Set([tab1Id, tab2Id]),
      activeTabId: tab2Id
    })

    const { container } = renderWithRouter()

    const tabPanels = container.querySelectorAll('[role="tabpanel"]')
    expect(tabPanels).toHaveLength(2)

    // Find the active and inactive panels
    const activePanel = Array.from(tabPanels).find(
      (panel) => (panel as HTMLElement).style.visibility === 'visible'
    )
    const inactivePanel = Array.from(tabPanels).find(
      (panel) => (panel as HTMLElement).style.visibility === 'hidden'
    )

    // Active tab should be visible
    expect(activePanel).toBeDefined()
    expect((activePanel as HTMLElement).style.visibility).toBe('visible')
    expect((activePanel as HTMLElement).style.position).toBe('relative')
    expect((activePanel as HTMLElement).style.pointerEvents).toBe('auto')

    // Inactive tab should be hidden
    expect(inactivePanel).toBeDefined()
    expect((inactivePanel as HTMLElement).style.visibility).toBe('hidden')
    expect((inactivePanel as HTMLElement).style.position).toBe('absolute')
    expect((inactivePanel as HTMLElement).style.pointerEvents).toBe('none')
  })

  it('renders correct view component based on tab type', () => {
    const { openTab } = useUIStore.getState()

    openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    openTab({
      type: 'project' as TabType,
      entityId: 'project1',
      title: 'Project 1'
    })

    openTab({
      type: 'codebase' as TabType,
      entityId: 'codebase1',
      title: 'Codebase 1'
    })

    openTab({
      type: 'settings' as TabType,
      entityId: 'main',
      title: 'Settings'
    })

    const { queryByTestId } = renderWithRouter()

    // All tabs should be visited on open, so all should render
    expect(queryByTestId('home-view')).toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).toBeInTheDocument()
    expect(queryByTestId('project-view-project1')).toBeInTheDocument()
    expect(queryByTestId('codebase-view-codebase1')).toBeInTheDocument()
    expect(queryByTestId('settings-view')).toBeInTheDocument()
  })

  it('maintains tab content when switching between visited tabs', () => {
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

    const { queryByTestId, rerender } = renderWithRouter()

    // Both tabs should be rendered
    expect(queryByTestId('home-view')).toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).toBeInTheDocument()

    // Switch to tab1
    switchTab(tab1Id)
    rerender(
      <MemoryRouter>
        <TabContentContainer />
      </MemoryRouter>
    )

    // Both tabs should still be rendered (visited and mounted)
    expect(queryByTestId('home-view')).toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).toBeInTheDocument()

    // Switch back to tab2
    switchTab(tab2Id)
    rerender(
      <MemoryRouter>
        <TabContentContainer />
      </MemoryRouter>
    )

    // Both tabs should still be rendered
    expect(queryByTestId('home-view')).toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).toBeInTheDocument()
  })

  it('renders active tab even if not in visitedTabs set', () => {
    const { openTab } = useUIStore.getState()

    const tab1Id = openTab({
      type: 'home' as TabType,
      entityId: 'main',
      title: 'Home'
    })

    openTab({
      type: 'task' as TabType,
      entityId: 'task1',
      title: 'Task 1'
    })

    // Clear visitedTabs but keep tab1 as active
    useUIStore.setState({
      visitedTabs: new Set(),
      activeTabId: tab1Id
    })

    const { queryByTestId } = renderWithRouter()

    // Active tab should render even if not in visitedTabs
    expect(queryByTestId('home-view')).toBeInTheDocument()
    expect(queryByTestId('task-view-task1')).not.toBeInTheDocument()
  })

  it('renders codebase tabs correctly', () => {
    const { openTab } = useUIStore.getState()

    openTab({
      type: 'codebase' as TabType,
      entityId: 'codebase123',
      title: 'My Codebase'
    })

    const { queryByTestId } = renderWithRouter()

    // Codebase tab should render with correct ID
    expect(queryByTestId('codebase-view-codebase123')).toBeInTheDocument()
    expect(queryByTestId('codebase-view-codebase123')).toHaveTextContent('Codebase Detail codebase123')
  })
})
