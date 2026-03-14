import type { ReactNode } from 'react'
import TabBar from './TabBar'
import NavigationMenu from './NavigationMenu'
import NotificationsPanel from '../notifications/NotificationsPanel'
import GitHubPRDropdown from '../github/GitHubPRDropdown'
import ActiveExecutionsDropdown from '../executions/ActiveExecutionsDropdown'
import ConversationsPanel from '../conversations/ConversationsPanel'
import CreateTaskModal from '../modals/CreateTaskModal'
import { useUIStore } from '../../stores/uiStore'
import { useActiveExecutions } from '../../hooks/useActiveExecutions'

interface AppShellProps {
  children: ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const { createTaskModalOpen, closeCreateTaskModal, conversationsPanelCollapsed, toggleConversationsPanel } = useUIStore()
  const { data: activeExecutions, loading: activeExecutionsLoading, refetch: refetchActiveExecutions } = useActiveExecutions(false)

  return (
    <div className="h-screen bg-gray-50 dark:bg-gray-900 flex flex-row">
      {/* Left: Navigation Sidebar */}
      <NavigationMenu />

      {/* Conversations Panel */}
      <ConversationsPanel
        activeExecutions={activeExecutions}
        collapsed={conversationsPanelCollapsed}
        onToggleCollapse={toggleConversationsPanel}
      />

      {/* Right column */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top strip - matches sidebar logo height */}
        <div className="h-16 flex items-center px-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0 gap-2">
          <div className="flex-1" />
          <ActiveExecutionsDropdown
            data={activeExecutions}
            loading={activeExecutionsLoading}
            refetch={refetchActiveExecutions}
          />
          <GitHubPRDropdown />
          <NotificationsPanel />
        </div>

        {/* Tab bar row */}
        <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex-shrink-0">
          <TabBar />
        </div>

        {/* Main Content */}
        <main className="flex-1 min-w-0 py-4 px-4 sm:px-6 lg:px-8 overflow-hidden">
          {children}
        </main>
      </div>
      {createTaskModalOpen && (
        <CreateTaskModal isOpen={createTaskModalOpen} onClose={closeCreateTaskModal} />
      )}
    </div>
  )
}
