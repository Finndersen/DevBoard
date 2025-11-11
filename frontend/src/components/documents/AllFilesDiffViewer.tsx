import { ArrowPathIcon } from '@heroicons/react/24/outline'
import type { TaskDiffResponse } from '../../lib/api'
import GitDiffViewer from './GitDiffViewer'

interface AllFilesDiffViewerProps {
  diffResponse: TaskDiffResponse | null
  loading: boolean
  onRefresh: () => void
  lastUpdated: string | null
  className?: string
}

export default function AllFilesDiffViewer({
  diffResponse,
  loading,
  onRefresh,
  lastUpdated,
  className = ''
}: AllFilesDiffViewerProps) {
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
  if (diffResponse && diffResponse.files.length === 0) {
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
              onClick={onRefresh}
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
      {/* Header with stats and refresh */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center space-x-4">
          {diffResponse && (
            <>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
                {diffResponse.files.length} file{diffResponse.files.length !== 1 ? 's' : ''} changed
              </h3>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                <span className="text-green-600 dark:text-green-400">
                  +{diffResponse.total_additions}
                </span>
                {' '}
                <span className="text-red-600 dark:text-red-400">
                  -{diffResponse.total_deletions}
                </span>
              </span>
            </>
          )}
        </div>
        <div className="flex items-center space-x-3">
          {lastUpdated && (
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Last updated: {formatTimestamp(lastUpdated)}
            </span>
          )}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <ArrowPathIcon className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* File diffs */}
      <div className="space-y-4 overflow-y-auto flex-1">
        {diffResponse?.files.map((file, index) => (
          <GitDiffViewer
            key={`${file.file_path}-${index}`}
            diff={file.diff_content}
            fileName={file.file_path}
            stats={{ additions: file.additions, deletions: file.deletions }}
          />
        ))}
      </div>
    </div>
  )
}
