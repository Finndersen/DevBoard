import { useState, useRef, useEffect, useCallback } from 'react'
import { ArrowPathIcon, ArrowTopRightOnSquareIcon, ChatBubbleLeftIcon, DocumentTextIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { useUIStore } from '../../stores/uiStore'
import type { OpenPRItem, OpenPRsResponse } from '../../lib/api'
import { StatusIndicator, ReviewBadge } from './PRStatusComponents'
import { surfaces, borderColors, textColors } from '../../styles/designSystem'

function getRepoShortName(fullName: string): string {
  const parts = fullName.split('/')
  return parts[parts.length - 1]
}

function formatRelativeTime(dateString: string): string {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const diffMs = now - then
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function PRIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="currentColor">
      <path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z" />
    </svg>
  )
}

interface GitHubPRDropdownProps {
  data: OpenPRsResponse | null
  loading: boolean
  refetch: (forceRefresh?: boolean) => void
}

export default function GitHubPRDropdown({ data, loading, refetch }: GitHubPRDropdownProps) {
  const navigateTo = useUIStore(s => s.navigateTo)
  const [isOpen, setIsOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  const prCount = data?.prs.length ?? 0
  const hasErrors = (data?.errors.length ?? 0) > 0

  const handleRefresh = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    refetch(true)
  }, [refetch])

  const handleOpenTask = (e: React.MouseEvent, pr: OpenPRItem) => {
    e.stopPropagation()
    if (pr.task_id) {
      navigateTo({ type: 'task', entityId: String(pr.task_id), title: pr.task_title || `Task #${pr.task_id}` })
      setIsOpen(false)
    }
  }

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-md text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        aria-label="Pull Requests"
      >
        <PRIcon className="w-5 h-5" />
        {prCount > 0 && (
          <span className="absolute top-0 right-0 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-blue-500 rounded-full">
            {prCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className={`absolute right-0 mt-2 w-96 ${surfaces.raised} rounded-lg shadow-lg border ${borderColors.default} z-50`}>
          {/* Header */}
          <div className={`p-4 border-b ${borderColors.default} flex items-center justify-between`}>
            <h3 className={`text-lg font-semibold ${textColors.primary}`}>
              Pull Requests ({prCount})
            </h3>
            <div className="flex items-center gap-2">
              {hasErrors && (
                <div title={data?.errors.join('\n')}>
                  <ExclamationTriangleIcon className="w-4 h-4 text-yellow-500" />
                </div>
              )}
              <button
                onClick={handleRefresh}
                className="p-1 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="Refresh PRs"
              >
                <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Scrollable list */}
          <div className="max-h-96 overflow-y-auto">
            {loading && !data && (
              <div className="p-8 text-center">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto" />
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Loading PRs...</p>
              </div>
            )}

            {data && data.prs.length === 0 && !loading && (
              <div className="p-8 text-center">
                <PRIcon className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                  {hasErrors ? 'PR status unavailable' : 'No open PRs'}
                </p>
              </div>
            )}

            {data && data.prs.length > 0 && (
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {data.prs.map(pr => (
                  <div
                    key={`${pr.repo_full_name}#${pr.pr_number}`}
                    className="p-3 hover:bg-gray-50 dark:hover:bg-white/[0.05] transition-colors"
                  >
                    <div className="flex items-start gap-2">
                      {/* Combined status indicator */}
                      <div className="flex-shrink-0 mt-0.5">
                        <StatusIndicator
                          mergeableState={pr.mergeable_state}
                          ciStatus={pr.ci_status}
                          reviewDecision={pr.review_decision}
                        />
                      </div>

                      {/* PR info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">
                            {getRepoShortName(pr.repo_full_name)} #{pr.pr_number}
                          </span>
                          <span className="text-xs text-gray-400 dark:text-gray-500">
                            {formatRelativeTime(pr.updated_at)}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400 truncate">{pr.title}</p>

                        {/* Review and comments */}
                        <div className="flex items-center gap-2 mt-1">
                          <ReviewBadge decision={pr.review_decision} />
                          {pr.comment_count > 0 && (
                            <span className="flex items-center gap-0.5 text-xs text-gray-400 dark:text-gray-500" title={`${pr.comment_count} comment${pr.comment_count !== 1 ? 's' : ''}`}>
                              <ChatBubbleLeftIcon className="w-3 h-3" />
                              {pr.comment_count}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          onClick={() => window.open(pr.pr_url, '_blank')}
                          className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                          title="Open in GitHub"
                        >
                          <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
                        </button>
                        {pr.task_id !== null && (
                          <button
                            onClick={(e) => handleOpenTask(e, pr)}
                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                            title="Open task"
                          >
                            <DocumentTextIcon className="w-3.5 h-3.5 text-gray-500 dark:text-gray-400" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
