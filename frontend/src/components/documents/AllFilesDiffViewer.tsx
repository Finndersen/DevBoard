import { ArrowPathIcon, CheckCircleIcon, EyeIcon } from '@heroicons/react/24/outline'
import { useState } from 'react'
import type { TaskDiffResponse, TaskBranchInfo } from '../../lib/api'
import type { CodeReviewStatus } from '../../views/hooks/useCodeReviewStatus'
import { DiffReviewProvider, type CommentSubmitHandler } from '../../contexts/DiffReviewContext'
import GitDiffViewer from './GitDiffViewer'
import SubmitAllCommentsButton from './SubmitAllCommentsButton'

interface AllFilesDiffViewerProps {
  branchInfo: TaskBranchInfo | null
  diffResponse: TaskDiffResponse | null
  loading: boolean
  onRefresh: (view: string) => void
  lastUpdated: string | null
  className?: string
  onSubmitComments?: CommentSubmitHandler
  codeReviewStatus?: CodeReviewStatus
  onAutoReview?: () => void
  isStreaming?: boolean
}

function AllFilesDiffViewerContent({
  branchInfo,
  diffResponse,
  loading,
  onRefresh,
  lastUpdated,
  className = '',
  onSubmitComments,
  codeReviewStatus,
  onAutoReview,
  isStreaming,
}: AllFilesDiffViewerProps) {
  // Track selected view
  const [selectedView, setSelectedView] = useState<string>('all')

  const handleViewChange = (view: string) => {
    setSelectedView(view)
    onRefresh(view)
  }

  // Get files to display from current response
  const displayFiles = diffResponse?.files || []

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`

    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`

    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
  }

  // Empty state - no changes
  if (diffResponse && displayFiles.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 ${className}`}>
        <div className="text-center max-w-md">
          <svg
            className="mx-auto h-12 w-12 text-gray-400 dark:text-gray-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">No file changes yet</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            When files are modified, they will appear here
          </p>
          <div className="mt-4">
            <button
              onClick={() => onRefresh(selectedView)}
              disabled={loading}
              className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ArrowPathIcon className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header with stats, view selector, and refresh */}
      <div className="space-y-3 mb-4 pb-4 border-b border-gray-200 dark:border-gray-700">
        {/* Stats row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {diffResponse && branchInfo && (
              <>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                  {branchInfo.commits.length} commit{branchInfo.commits.length !== 1 ? 's' : ''}
                  {branchInfo.has_uncommitted_changes && <span className="text-gray-500 dark:text-gray-400"> + uncommitted</span>}
                </h3>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {displayFiles.length} file{displayFiles.length !== 1 ? 's' : ''} in view
                </span>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  <span className="text-green-600 dark:text-green-400">
                    +{diffResponse.additions}
                  </span>
                  {' '}
                  <span className="text-red-600 dark:text-red-400">
                    -{diffResponse.deletions}
                  </span>
                </span>
              </>
            )}
          </div>
          <div className="flex items-center space-x-2">
            {/* Submit All Comments Button - only visible when there are pending comments */}
            {onSubmitComments && <SubmitAllCommentsButton />}
            {/* Auto-Review split button: [👁 Auto-Review | status icon] */}
            {onAutoReview && (
              <div className="inline-flex items-center rounded-md border border-gray-300 dark:border-gray-600 overflow-hidden">
                <button
                  onClick={onAutoReview}
                  disabled={isStreaming}
                  className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <EyeIcon className="w-3.5 h-3.5 mr-1" />
                  Auto-Review
                </button>
                <div className="w-px self-stretch bg-gray-300 dark:bg-gray-600" />
                <div className="flex items-center justify-center w-7 bg-white dark:bg-gray-800">
                  {codeReviewStatus === 'reviewed'
                    ? <CheckCircleIcon className="w-3.5 h-3.5 text-green-500" />
                    : <span className="w-2 h-2 rounded-full border border-gray-400 dark:border-gray-500" />
                  }
                </div>
              </div>
            )}
            {/* Refresh: timestamp + icon-only button */}
            <div className="flex items-center space-x-1">
              {lastUpdated && (
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  {formatTimestamp(lastUpdated)}
                </span>
              )}
              <button
                onClick={() => onRefresh(selectedView)}
                disabled={loading}
                title="Refresh"
                className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ArrowPathIcon className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>

        {/* View selector row */}
        <div>
          <select
            id="view-select"
            value={selectedView}
            onChange={(e) => handleViewChange(e.target.value)}
            disabled={loading}
            className="w-full text-sm px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md text-gray-900 dark:text-gray-100 hover:border-gray-400 dark:hover:border-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="all">All Changes (Combined)</option>
            {branchInfo?.commits.map((commit) => (
              <option key={commit.commit_hash} value={commit.commit_hash}>
                {commit.commit_hash.substring(0, 7)} - {commit.message}
              </option>
            ))}
            {branchInfo?.has_uncommitted_changes && (
              <option value="uncommitted">Uncommitted Changes</option>
            )}
          </select>
        </div>
      </div>

      {/* File diffs - flat view based on selected option */}
      <div className="space-y-3 overflow-y-auto flex-1">
        {displayFiles.map((file, fileIndex) => (
          <GitDiffViewer
            key={`file-${fileIndex}-${file.file_path}`}
            diff={file.diff_content}
            fileName={file.file_path}
            stats={{ additions: file.additions, deletions: file.deletions }}
            isNewFile={file.is_new_file}
            isDeleted={file.is_deleted}
          />
        ))}
      </div>
    </div>
  )
}

export default function AllFilesDiffViewer(props: AllFilesDiffViewerProps) {
  // If onSubmitComments is provided, wrap content with DiffReviewProvider to enable comments
  if (props.onSubmitComments) {
    return (
      <DiffReviewProvider onSubmitComments={props.onSubmitComments}>
        <AllFilesDiffViewerContent {...props} />
      </DiffReviewProvider>
    )
  }

  // Without onSubmitComments, render without provider (comments disabled)
  return <AllFilesDiffViewerContent {...props} />
}
