import { useState, useRef, useEffect, useCallback } from 'react'
import { ArrowPathIcon, ArrowTopRightOnSquareIcon, DocumentTextIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { useOpenPRs } from '../../hooks/useGitHubPRs'
import { useUIStore } from '../../stores/uiStore'
import { apiClient } from '../../lib/api'
import type { OpenPRItem, PRDetailResponse } from '../../lib/api'

function getStatusDotClass(mergeableState: string | null): string {
  switch (mergeableState) {
    case 'clean':
      return 'bg-green-500'
    case 'dirty':
    case 'unstable':
      return 'bg-red-500'
    default:
      return 'bg-yellow-500'
  }
}

function getRepoShortName(fullName: string): string {
  const parts = fullName.split('/')
  return parts[parts.length - 1]
}

interface PRDetailPopoverProps {
  pr: OpenPRItem
  onClose: () => void
}

function PRDetailPopover({ pr, onClose }: PRDetailPopoverProps) {
  const [detail, setDetail] = useState<PRDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    apiClient.getPRDetail(pr.codebase_id, pr.pr_number)
      .then(data => {
        if (!cancelled) {
          setDetail(data)
          setLoading(false)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load details')
          setLoading(false)
        }
      })

    return () => { cancelled = true }
  }, [pr.codebase_id, pr.pr_number])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  const getCIIcon = (state: string) => {
    switch (state) {
      case 'success': return '✓'
      case 'failure':
      case 'error': return '✗'
      default: return '○'
    }
  }

  const getCIColor = (state: string) => {
    switch (state) {
      case 'success': return 'text-green-500'
      case 'failure':
      case 'error': return 'text-red-500'
      default: return 'text-yellow-500'
    }
  }

  const getReviewIcon = (state: string) => {
    switch (state) {
      case 'APPROVED': return '✓'
      case 'CHANGES_REQUESTED': return '✗'
      default: return '💬'
    }
  }

  const getReviewColor = (state: string) => {
    switch (state) {
      case 'APPROVED': return 'text-green-500'
      case 'CHANGES_REQUESTED': return 'text-red-500'
      default: return 'text-gray-400'
    }
  }

  return (
    <div
      ref={popoverRef}
      className="absolute top-full left-0 mt-1 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50 p-3"
    >
      {loading && (
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500" />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      {detail && (
        <div className="space-y-3">
          {/* CI Checks */}
          <div>
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">CI Status</span>
              {detail.ci_status && (
                <span className={`text-xs font-medium ${getCIColor(detail.ci_status)}`}>
                  ({detail.ci_status})
                </span>
              )}
            </div>
            {detail.checks.length > 0 ? (
              <ul className="space-y-0.5">
                {detail.checks.map((check, i) => (
                  <li key={i} className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                    <span className={getCIColor(check.state)}>{getCIIcon(check.state)}</span>
                    <span className="truncate">{check.name}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-gray-500">No checks</p>
            )}
          </div>

          {/* Reviews */}
          <div>
            <span className="text-xs font-medium text-gray-700 dark:text-gray-300">Reviews</span>
            {detail.reviews.length > 0 ? (
              <ul className="space-y-0.5 mt-1">
                {detail.reviews.map((review, i) => (
                  <li key={i} className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                    <span className={getReviewColor(review.state)}>{getReviewIcon(review.state)}</span>
                    <span className="truncate">{review.author}</span>
                    <span className="text-gray-500">({review.state.toLowerCase().replace('_', ' ')})</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-gray-500 mt-1">No reviews</p>
            )}
          </div>

          {/* Comment count */}
          <div className="text-xs text-gray-500">
            {detail.review_comment_count} review comment{detail.review_comment_count !== 1 ? 's' : ''}
          </div>
        </div>
      )}
    </div>
  )
}

export default function GitHubPRStatusBar() {
  const { data, loading, error, refetch } = useOpenPRs()
  const openTab = useUIStore(s => s.openTab)
  const [expandedPR, setExpandedPR] = useState<{ codebaseId: number; prNumber: number } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const handleRefresh = useCallback(() => {
    setExpandedPR(null)
    refetch()
  }, [refetch])

  const handlePillClick = (pr: OpenPRItem) => {
    if (expandedPR?.codebaseId === pr.codebase_id && expandedPR?.prNumber === pr.pr_number) {
      setExpandedPR(null)
    } else {
      setExpandedPR({ codebaseId: pr.codebase_id, prNumber: pr.pr_number })
    }
  }

  const handleOpenTask = (pr: OpenPRItem) => {
    if (pr.task_id) {
      openTab({ type: 'task', entityId: String(pr.task_id), title: pr.task_title || `Task #${pr.task_id}` })
    }
  }

  if (!data && !loading && !error) return null

  return (
    <div className="flex items-center gap-2 flex-1 min-w-0 overflow-hidden" ref={containerRef}>
      {/* Refresh button */}
      <button
        onClick={handleRefresh}
        className="flex-shrink-0 p-1 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        title="Refresh PRs"
      >
        <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
      </button>

      {/* Error warning */}
      {data && data.errors.length > 0 && (
        <div className="flex-shrink-0" title={data.errors.join('\n')}>
          <ExclamationTriangleIcon className="w-4 h-4 text-yellow-500" />
        </div>
      )}

      {/* Loading state */}
      {loading && !data && (
        <span className="text-xs text-gray-500 dark:text-gray-400">Loading PRs...</span>
      )}

      {/* Empty state */}
      {data && data.prs.length === 0 && !loading && (
        <span className="text-xs text-gray-500 dark:text-gray-400">No open PRs</span>
      )}

      {/* PR pills */}
      {data && data.prs.length > 0 && (
        <div className="flex items-center gap-1.5 overflow-x-auto flex-nowrap min-w-0">
          {data.prs.map(pr => (
            <div key={`${pr.codebase_id}-${pr.pr_number}`} className="relative flex-shrink-0">
              <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-700 text-xs">
                {/* Status dot */}
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${getStatusDotClass(pr.mergeable_state)}`} />

                {/* Clickable PR info */}
                <button
                  onClick={() => handlePillClick(pr)}
                  className="flex items-center gap-1 hover:text-blue-600 dark:hover:text-blue-400 transition-colors text-gray-700 dark:text-gray-300 max-w-48"
                >
                  <span className="font-medium whitespace-nowrap">{getRepoShortName(pr.repo_full_name)} #{pr.pr_number}</span>
                  <span className="truncate text-gray-500 dark:text-gray-400">{pr.title}</span>
                </button>

                {/* Action buttons */}
                <button
                  onClick={() => window.open(pr.pr_url, '_blank')}
                  className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex-shrink-0"
                  title="Open in GitHub"
                >
                  <ArrowTopRightOnSquareIcon className="w-3 h-3 text-gray-500 dark:text-gray-400" />
                </button>

                {pr.task_id !== null && (
                  <button
                    onClick={() => handleOpenTask(pr)}
                    className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex-shrink-0"
                    title="Open task"
                  >
                    <DocumentTextIcon className="w-3 h-3 text-gray-500 dark:text-gray-400" />
                  </button>
                )}
              </div>

              {/* Expanded detail popover */}
              {expandedPR?.codebaseId === pr.codebase_id && expandedPR?.prNumber === pr.pr_number && (
                <PRDetailPopover pr={pr} onClose={() => setExpandedPR(null)} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
