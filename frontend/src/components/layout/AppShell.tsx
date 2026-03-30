import { useCallback, useEffect } from 'react'
import { ChatBubbleLeftRightIcon, ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import { surfaces, borderColors, hoverColors } from '../../styles/designSystem'
import NavigationMenu from './NavigationMenu'
import ViewContainer from './ViewContainer'
import NotificationsPanel from '../notifications/NotificationsPanel'
import GitHubPRDropdown from '../github/GitHubPRDropdown'
import ConversationsPanel from '../conversations/ConversationsPanel'
import CreateTaskModal from '../modals/CreateTaskModal'
import { useUIStore } from '../../stores/uiStore'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useStreamBootstrap } from '../../hooks/useStreamBootstrap'
import { useStreamHealthCheck } from '../../hooks/useStreamHealthCheck'
import { useURLSync } from '../../hooks/useURLSync'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { webSocketManager } from '../../services/WebSocketManager'
import { usePRStatusPolling } from '../../hooks/usePRStatusPolling'

export default function AppShell() {
  const {
    createTaskModalOpen,
    closeCreateTaskModal,
    conversationsPanelCollapsed,
    toggleConversationsPanel,
    unreadConversationIds,
  } = useUIStore()

  const streamingCount = useConversationStreamStore(
    useCallback((state) => {
      let count = 0
      for (const [, stream] of state.activeStreams) {
        if (stream.isStreaming) count++
      }
      return count
    }, [])
  )

  const unreadCount = unreadConversationIds.length

  // Initialize the always-open WebSocket connection
  useEffect(() => {
    webSocketManager.setEventHandler((conversationId, event) => {
      useConversationStreamStore.getState().handleWebSocketEvent(conversationId, event)
    })
    webSocketManager.initialize()
    return () => webSocketManager.destroy()
  }, [])

  // Bootstrap active streams on app startup
  useStreamBootstrap()

  // Periodic health check to reconnect orphaned streams
  useStreamHealthCheck()

  // Synchronize URL with view state
  useURLSync()

  // Enable global keyboard shortcuts
  useKeyboardShortcuts()

  // Periodic polling to keep backend PR cache warm
  const { data: prData, loading: prLoading, refetch: refetchPRs } = usePRStatusPolling()

  return (
    <div className="h-screen bg-gray-50 dark:bg-gray-900 flex flex-row">
      {/* Left: Navigation Sidebar */}
      <NavigationMenu />

      {/* Right column (conversations panel + main content share the top strip) */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top strip */}
        <div className={`h-16 flex items-center border-b ${borderColors.default} ${surfaces.raised} flex-shrink-0`}>
          {/* Conversations toggle — fixed w-80 when expanded, auto when collapsed */}
          <button
            onClick={toggleConversationsPanel}
            className={`h-full w-80 flex items-center gap-2 px-3 border-r ${borderColors.default} ${hoverColors.subtle} transition-colors shrink-0`}
            aria-label={conversationsPanelCollapsed ? 'Expand conversations' : 'Collapse conversations'}
          >
            <ChatBubbleLeftRightIcon className="w-5 h-5 text-gray-500 dark:text-gray-400 shrink-0" />
            <span className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex-1 text-left">
              Conversations
            </span>
            <div className="flex items-center gap-1.5">
              {streamingCount > 0 && (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-1.5 rounded-full h-5 bg-emerald-50 text-emerald-600 border border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  {streamingCount}
                </span>
              )}
              {unreadCount > 0 && (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-1.5 rounded-full h-5 bg-blue-50 text-blue-600 border border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                  {unreadCount}
                </span>
              )}
            </div>
            {conversationsPanelCollapsed ? (
              <ChevronRightIcon className="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0" />
            ) : (
              <ChevronLeftIcon className="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0" />
            )}
          </button>

          <div className="flex-1" />
          <div className="flex items-center gap-2 px-4">
            <GitHubPRDropdown data={prData} loading={prLoading} refetch={refetchPRs} />
            <NotificationsPanel />
          </div>
        </div>

        {/* Content row: conversations panel + main content */}
        <div className="flex flex-1 min-h-0">
          {/* Conversations Panel */}
          <ConversationsPanel />

          {/* Main Content */}
          <main className="flex-1 min-w-0 py-2 px-3 sm:px-4 lg:px-5 overflow-hidden">
            <ViewContainer />
          </main>
        </div>
      </div>

      {createTaskModalOpen && (
        <CreateTaskModal isOpen={createTaskModalOpen} onClose={closeCreateTaskModal} />
      )}
    </div>
  )
}
