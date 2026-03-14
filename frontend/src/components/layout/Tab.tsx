import type { MouseEvent, ReactNode } from 'react'
import {
  XMarkIcon,
  FolderIcon,
  ClipboardDocumentListIcon,
  CodeBracketIcon,
  Cog6ToothIcon,
  HomeIcon,
  PuzzlePieceIcon
} from '@heroicons/react/24/outline'
import type { TabState, ActivityStatus, TabType } from '../../stores/uiStore'

interface TabProps {
  tab: TabState
  isActive: boolean
  onSelect: () => void
  onClose: (e: MouseEvent) => void
}

function PulsingGreenDot() {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
    </span>
  )
}

function getActivityIndicator(status: ActivityStatus): ReactNode {
  switch (status.type) {
    case 'new_messages':
      return `●${status.count > 1 ? status.count : ''}`
    case 'agent_working':
      return <PulsingGreenDot />
    case 'action_required':
      return '🔴'
    case 'idle':
    default:
      return null
  }
}

function getActivityColor(status: ActivityStatus): string {
  switch (status.type) {
    case 'new_messages':
      return 'text-blue-600 dark:text-blue-400'
    case 'agent_working':
      return ''
    case 'action_required':
      return 'text-red-600 dark:text-red-400'
    default:
      return ''
  }
}

function getTabIcon(type: TabType): React.ReactNode {
  const iconClassName = 'w-4 h-4'

  switch (type) {
    case 'project':
      return <FolderIcon className={iconClassName} />
    case 'task':
      return <ClipboardDocumentListIcon className={iconClassName} />
    case 'codebase':
      return <CodeBracketIcon className={iconClassName} />
    case 'settings':
      return <Cog6ToothIcon className={iconClassName} />
    case 'home':
      return <HomeIcon className={iconClassName} />
    case 'mcp-servers':
      return <PuzzlePieceIcon className={iconClassName} />
  }
}

export default function Tab({ tab, isActive, onSelect, onClose }: TabProps) {
  const activityIndicator = getActivityIndicator(tab.activityStatus)
  const activityColor = getActivityColor(tab.activityStatus)
  const icon = getTabIcon(tab.type)

  return (
    <div
      className={`
        group relative flex items-center gap-2 px-3 py-2 border-b-2 cursor-pointer
        transition-colors duration-150 min-w-[140px] max-w-[220px]
        ${
          isActive
            ? 'border-blue-600 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
            : 'border-transparent hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
        }
      `}
      onClick={onSelect}
      title={`${tab.title}\nLast activity: ${new Date(tab.lastActivity).toLocaleString()}`}
    >
      {/* Activity Indicator */}
      {activityIndicator && (
        <span className={`text-sm font-medium ${activityColor}`}>
          {activityIndicator}
        </span>
      )}

      {/* Tab Icon */}
      <span className="flex-shrink-0">
        {icon}
      </span>

      {/* Tab Title */}
      <span className="flex-1 truncate text-sm font-medium">
        {tab.title}
      </span>

      {/* Unsaved Changes Indicator */}
      {tab.hasUnsavedChanges && (
        <span className="text-orange-500 dark:text-orange-400 text-xs">
          *
        </span>
      )}

      {/* Close Button */}
      <button
        onClick={onClose}
        className={`
          p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600
          opacity-0 group-hover:opacity-100 transition-opacity
          ${isActive ? 'opacity-100' : ''}
        `}
        aria-label="Close tab"
      >
        <XMarkIcon className="w-4 h-4" />
      </button>
    </div>
  )
}
