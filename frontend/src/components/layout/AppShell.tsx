import { ChatBubbleLeftRightIcon, ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import NavigationMenu from './NavigationMenu'
import ViewContainer from './ViewContainer'
import NotificationsPanel from '../notifications/NotificationsPanel'
import GitHubPRDropdown from '../github/GitHubPRDropdown'
import ConversationsPanel from '../conversations/ConversationsPanel'
import CreateTaskModal from '../modals/CreateTaskModal'
import { useUIStore } from '../../stores/uiStore'
import { useStreamBootstrap } from '../../hooks/useStreamBootstrap'
import { useURLSync } from '../../hooks/useURLSync'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'

export default function AppShell() {
  const {
    createTaskModalOpen,
    closeCreateTaskModal,
    conversationsPanelCollapsed,
    toggleConversationsPanel,
    unreadConversationIds,
  } = useUIStore()

  // Bootstrap active streams on app startup
  useStreamBootstrap()

  // Synchronize URL with view state
  useURLSync()

  // Enable global keyboard shortcuts
  useKeyboardShortcuts()

  return (
    <div className="h-screen bg-gray-50 dark:bg-gray-900 flex flex-row">
      {/* Left: Navigation Sidebar */}
      <NavigationMenu />

      {/* Right column (conversations panel + main content share the top strip) */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top strip */}
        <div className="h-16 flex items-center border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0">
          {/* Conversations toggle — fixed w-80 when expanded, auto when collapsed */}
          <button
            onClick={toggleConversationsPanel}
            className="h-full w-80 flex items-center gap-2 px-3 border-r border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors shrink-0"
            aria-label={conversationsPanelCollapsed ? 'Expand conversations' : 'Collapse conversations'}
          >
            <div className="relative shrink-0">
              <ChatBubbleLeftRightIcon className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              {conversationsPanelCollapsed && unreadConversationIds.length > 0 && (
                <span className="absolute -top-1.5 -right-2 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
                  {unreadConversationIds.length}
                </span>
              )}
            </div>
            <span className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex-1 text-left">
              Conversations
            </span>
            {conversationsPanelCollapsed ? (
              <ChevronRightIcon className="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0" />
            ) : (
              <ChevronLeftIcon className="w-4 h-4 text-gray-500 dark:text-gray-400 shrink-0" />
            )}
          </button>

          <div className="flex-1" />
          <div className="flex items-center gap-2 px-4">
            <GitHubPRDropdown />
            <NotificationsPanel />
          </div>
        </div>

        {/* Content row: conversations panel + main content */}
        <div className="flex flex-1 min-h-0">
          {/* Conversations Panel */}
          <ConversationsPanel />

          {/* Main Content */}
          <main className="flex-1 min-w-0 py-4 px-3 sm:px-4 lg:px-5 overflow-hidden">
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
