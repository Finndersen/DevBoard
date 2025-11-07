import { useMemo } from 'react'
import { useUIStore } from '../../stores/uiStore'
import Home from '../../views/Home'
import TaskDetail from '../../views/TaskDetail'
import ProjectDetail from '../../views/ProjectDetail'
import CodebaseDetail from '../../views/CodebaseDetail'
import Settings from '../../views/Settings'

/**
 * Renders tabs with lazy mounting and CSS visibility toggling.
 * Tabs are only mounted when first opened, then kept mounted for fast switching.
 * Uses visibility:hidden instead of display:none to preserve layout calculations for hidden tabs.
 * This eliminates expensive browser reflow when switching tabs.
 * Components stay mounted even when hidden, preserving all state and ongoing operations.
 * This enables seamless multitasking where switching tabs doesn't interrupt streaming or lose state.
 * On page refresh, only the active tab is mounted initially, keeping initial load fast.
 */
export default function TabContentContainer() {
  const { tabs, activeTabId, visitedTabs } = useUIStore()

  // If no tabs are open, show loading state while URL sync happens
  if (tabs.length === 0) {
    return (
      <div className="w-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  // Memoize rendered tabs to prevent unnecessary re-renders of inactive tabs
  // Only render tabs that have been visited or are currently active (lazy mounting)
  const renderedTabs = useMemo(() => {
    return tabs.map((tab) => {
      const isActive = tab.id === activeTabId
      const hasBeenVisited = visitedTabs.has(tab.id)

      // Only render if tab is active or has been visited before
      if (!isActive && !hasBeenVisited) {
        return null
      }

      return (
        <div
          key={tab.id}
          role="tabpanel"
          aria-hidden={!isActive}
          style={{
            display: 'block',
            visibility: isActive ? 'visible' : 'hidden',
            position: isActive ? 'relative' : 'absolute',
            pointerEvents: isActive ? 'auto' : 'none'
          }}
        >
          {tab.type === 'home' && <Home />}
          {tab.type === 'task' && <TaskDetail id={tab.entityId} />}
          {tab.type === 'project' && <ProjectDetail id={tab.entityId} />}
          {tab.type === 'codebase' && <CodebaseDetail id={tab.entityId} />}
          {tab.type === 'settings' && <Settings />}
        </div>
      )
    })
  }, [tabs, activeTabId, visitedTabs])

  return <>{renderedTabs}</>
}
