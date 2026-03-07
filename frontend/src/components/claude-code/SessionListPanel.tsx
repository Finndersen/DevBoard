import { DocumentTextIcon } from '@heroicons/react/24/outline'
import { textColors } from '../../styles/designSystem'
import type { ClaudeCodeSession } from '../../lib/api'

interface SessionListPanelProps {
  sessions: ClaudeCodeSession[]
  selectedSessionId: string | null
  loading: boolean
  onSelect: (session: ClaudeCodeSession) => void
}

function formatRelativeTime(isoDate: string): string {
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMinutes = Math.floor(diffMs / 60000)

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

export function SessionListPanel({ sessions, selectedSessionId, loading, onSelect }: SessionListPanelProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="text-center py-8 px-4">
        <DocumentTextIcon className="w-10 h-10 mx-auto text-gray-400 mb-3" />
        <p className={`text-sm ${textColors.secondary}`}>No sessions found</p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-200 dark:divide-gray-700">
      {sessions.map(session => {
        const isSelected = session.session_id === selectedSessionId
        return (
          <button
            key={session.session_id}
            onClick={() => onSelect(session)}
            className={`w-full text-left px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
              isSelected ? 'bg-blue-50 dark:bg-blue-900/30 border-l-2 border-l-blue-500' : ''
            }`}
          >
            <div className="min-w-0">
              <p className={`text-sm ${textColors.primary} line-clamp-2 leading-snug`}>
                {session.label}
              </p>
              <div className={`flex items-center gap-2 mt-1 text-xs ${textColors.muted}`}>
                <span>{formatRelativeTime(session.last_activity)}</span>
                <span>·</span>
                <span>{formatFileSize(session.file_size)}</span>
              </div>
            </div>
          </button>
        )
      })}
    </div>
  )
}
