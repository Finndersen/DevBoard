import { DocumentTextIcon } from '@heroicons/react/24/outline'
import { useNavigate } from 'react-router-dom'
import { textColors } from '../../styles/designSystem'
import type { ClaudeCodeSession } from '../../lib/api'

interface SessionListPanelProps {
  sessions: ClaudeCodeSession[]
  selectedSessionId: string | null
  loading: boolean
  onSelect: (session: ClaudeCodeSession) => void
  matchCounts?: Map<string, number>
}

const AGENT_ROLE_LABELS: Record<string, string> = {
  task_planning: 'Planning',
  task_implementation: 'Implementation',
  task_pr_review: 'PR Review',
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

export function SessionListPanel({ sessions, selectedSessionId, loading, onSelect, matchCounts }: SessionListPanelProps) {
  const navigate = useNavigate()

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
      </div>
    )
  }

  const visibleSessions = sessions.filter(s => s.session_role !== 'implementation')

  if (visibleSessions.length === 0) {
    return (
      <div className="text-center py-8 px-4">
        <DocumentTextIcon className="w-10 h-10 mx-auto text-gray-400 mb-3" />
        <p className={`text-sm ${textColors.secondary}`}>No sessions found</p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-200 dark:divide-gray-700">
      {visibleSessions.map(session => {
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
              <p className={`text-sm ${textColors.primary} leading-snug flex items-start`}>
                <span className="line-clamp-2">{session.label}</span>
                {matchCounts?.get(session.session_id) ? (
                  <span className="ml-1.5 shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300">
                    {matchCounts.get(session.session_id)}
                  </span>
                ) : null}
              </p>
              <div className={`flex items-center gap-2 mt-1 text-xs ${textColors.muted}`}>
                <span>{formatRelativeTime(session.last_activity)}</span>
                <span>·</span>
                <span>{formatFileSize(session.file_size)}</span>
                {session.session_role === 'plan' && (
                  <>
                    <span>·</span>
                    <span className="text-blue-500 dark:text-blue-400 font-medium">Plan + Implement</span>
                  </>
                )}
              </div>
              {session.task_info && (
                <div className="mt-1 flex items-center gap-1.5 text-xs">
                  <span
                    role="link"
                    tabIndex={0}
                    className="text-blue-600 dark:text-blue-400 hover:underline cursor-pointer truncate"
                    onClick={e => {
                      e.stopPropagation()
                      navigate(`/tasks/${session.task_info!.task_id}`)
                    }}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.stopPropagation()
                        navigate(`/tasks/${session.task_info!.task_id}`)
                      }
                    }}
                  >
                    {session.task_info.task_title}
                  </span>
                  <span className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                    {AGENT_ROLE_LABELS[session.task_info.agent_role] ?? session.task_info.agent_role}
                  </span>
                </div>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}
