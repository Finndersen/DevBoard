import { useMemo } from 'react'
import { loadingSpinner } from '../../styles/designSystem'
import { useUIStore } from '../../stores/uiStore'
import { ViewContextProvider } from '../../contexts/ViewContext'
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

export default function ViewContainer() {
  const { cachedViews, activeViewId } = useUIStore()

  const renderedViews = useMemo(() => {
    if (cachedViews.length === 0) {
      return []
    }
    return cachedViews.map((view) => {
      const isActive = view.id === activeViewId

      return (
        <div
          key={view.id}
          role="tabpanel"
          aria-hidden={!isActive}
          style={{
            position: 'absolute',
            inset: 0,
            visibility: isActive ? 'visible' : 'hidden',
            pointerEvents: isActive ? 'auto' : 'none',
            zIndex: isActive ? 1 : 0,
          }}
        >
          <ViewContextProvider viewId={view.id} viewType={view.type} entityId={view.entityId}>
            {view.type === 'home' && <Home />}
            {view.type === 'task' && (
              <ConversationEventHandlerProvider>
                <TaskDetail id={view.entityId} />
              </ConversationEventHandlerProvider>
            )}
            {view.type === 'project' && (
              <ConversationEventHandlerProvider>
                <ProjectDetail id={view.entityId} />
              </ConversationEventHandlerProvider>
            )}
            {view.type === 'codebase' && <CodebaseDetail id={view.entityId} />}
            {view.type === 'projects-list' && <ProjectsList />}
            {view.type === 'codebases-list' && <CodebasesList />}
            {view.type === 'tasks-list' && <TasksList />}
            {view.type === 'mcp-servers' && <MCPServersView />}
            {view.type === 'settings' && <Settings />}
            {view.type === 'claude-code' && <ClaudeCodeView />}
          </ViewContextProvider>
        </div>
      )
    })
  }, [cachedViews, activeViewId])

  if (cachedViews.length === 0) {
    return (
      <div className="w-full flex items-center justify-center">
        <div className={loadingSpinner}></div>
      </div>
    )
  }

  return <div className="relative h-full">{renderedViews}</div>
}
