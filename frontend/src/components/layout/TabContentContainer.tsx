import { useMemo } from 'react'
import { useUIStore } from '../../stores/uiStore'
import Home from '../../views/Home'
import TaskDetail from '../../views/TaskDetail'
import ProjectDetail from '../../views/ProjectDetail'
import Settings from '../../views/Settings'

/**
 * Renders all open tabs with CSS visibility toggling.
 * Uses visibility:hidden instead of display:none to preserve layout calculations for hidden tabs.
 * This eliminates expensive browser reflow when switching tabs.
 * Components stay mounted even when hidden, preserving all state and ongoing operations.
 * This enables seamless multitasking where switching tabs doesn't interrupt streaming or lose state.
 */
export default function TabContentContainer() {
  const { tabs, activeTabId } = useUIStore()

  // If no tabs are open, show loading state while URL sync happens
  if (tabs.length === 0) {
    return (
      <div className="w-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  // Memoize rendered tabs to prevent unnecessary re-renders of inactive tabs
  // Only re-memoize when tabs array or activeTabId changes
  const renderedTabs = useMemo(() => {
    return tabs.map((tab) => {
      const isActive = tab.id === activeTabId

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
          {tab.type === 'settings' && <Settings />}
        </div>
      )
    })
  }, [tabs, activeTabId])

  return <>{renderedTabs}</>
}
