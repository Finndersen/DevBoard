import { useMemo } from 'react'
import { useUIStore } from '../../stores/uiStore'
import Home from '../../views/Home'
import TaskDetail from '../../views/TaskDetail'
import ProjectDetail from '../../views/ProjectDetail'
import CodebaseDetail from '../../views/CodebaseDetail'
import MCPServersView from '../../views/MCPServers'
import Settings from '../../views/Settings'
import ClaudeCodeView from '../../views/ClaudeCodeView'
import ProjectsList from '../../views/ProjectsList'
import CodebasesList from '../../views/CodebasesList'
import TasksList from '../../views/TasksList'
import ConversationEventHandlerProvider from '../chat/ConversationEventHandlerProvider'

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

  // Memoize rendered tabs to prevent unnecessary re-renders of inactive tabs
  // Only render tabs that have been visited or are currently active (lazy mounting)
  const renderedTabs = useMemo(() => {
    // If no tabs are open, return empty array
    if (tabs.length === 0) {
      return []
    }
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
            pointerEvents: isActive ? 'auto' : 'none',
            height: '100%',
            ...(isActive ? {} : { inset: 0 }),
          }}
        >
          {tab.type === 'home' && <Home />}
          {tab.type === 'task' && (
            <ConversationEventHandlerProvider>
              <TaskDetail id={tab.entityId} />
            </ConversationEventHandlerProvider>
          )}
          {tab.type === 'project' && (
            <ConversationEventHandlerProvider>
              <ProjectDetail id={tab.entityId} />
            </ConversationEventHandlerProvider>
          )}
          {tab.type === 'codebase' && <CodebaseDetail id={tab.entityId} />}
          {tab.type === 'projects-list' && <ProjectsList />}
          {tab.type === 'codebases-list' && <CodebasesList />}
          {tab.type === 'tasks-list' && <TasksList />}
          {tab.type === 'mcp-servers' && <MCPServersView />}
          {tab.type === 'settings' && <Settings />}
          {tab.type === 'claude-code' && <ClaudeCodeView />}
        </div>
      )
    })
  }, [tabs, activeTabId, visitedTabs])

  // If no tabs are open, show loading state while URL sync happens
  if (tabs.length === 0) {
    return (
      <div className="w-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return <>{renderedTabs}</>
}
