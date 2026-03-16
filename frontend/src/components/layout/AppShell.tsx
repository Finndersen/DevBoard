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
  const { createTaskModalOpen, closeCreateTaskModal } = useUIStore()

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

      {/* Conversations Panel */}
      <ConversationsPanel />

      {/* Right column */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top strip - matches sidebar logo height */}
        <div className="h-16 flex items-center px-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0 gap-2">
          <div className="flex-1" />
          <GitHubPRDropdown />
          <NotificationsPanel />
        </div>

        {/* Main Content */}
        <main className="flex-1 min-w-0 py-4 px-4 sm:px-6 lg:px-8 overflow-hidden">
          <ViewContainer />
        </main>
      </div>
      {createTaskModalOpen && (
        <CreateTaskModal isOpen={createTaskModalOpen} onClose={closeCreateTaskModal} />
      )}
    </div>
  )
}
