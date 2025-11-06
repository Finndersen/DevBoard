import { useState } from 'react'
import type { ToolCall, ToolResult } from '../../lib/api'
import { formatTimestamp, formatDuration } from '../../styles/messageStyles'

interface ToolCallDisplayProps {
  toolCall: ToolCall
  toolResult?: ToolResult
}

export default function ToolCallDisplay({ toolCall, toolResult }: ToolCallDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const hasResult = toolResult !== undefined
  const isError = toolResult?.is_error || false
  const hasArguments = toolCall.tool_args && Object.keys(toolCall.tool_args).length > 0

  // Determine status
  const status = isError ? 'error' : hasResult ? 'complete' : 'running'

  // Status icon and color
  const getStatusIcon = () => {
    if (status === 'running') {
      return (
        <svg className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      )
    } else if (status === 'error') {
      return (
        <svg className="w-4 h-4 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      )
    } else {
      return (
        <svg className="w-4 h-4 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      )
    }
  }

  const getStatusColor = () => {
    if (status === 'running') return 'border-blue-600 bg-blue-50 dark:bg-blue-900/10'
    if (status === 'error') return 'border-red-600 bg-red-50 dark:bg-red-900/10'
    return 'border-green-600 bg-green-50 dark:bg-green-900/10'
  }

  return (
    <div className="flex justify-start my-2">
      <div className="max-w-[80%] flex flex-col items-start">
        {/* Collapsed Tool Call Card */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`rounded-lg border ${getStatusColor()} overflow-hidden shadow-sm w-full text-left hover:opacity-80 transition-opacity`}
        >
          {/* Minimal Header */}
          <div className="px-3 py-2 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              {/* Tool Icon */}
              <svg
                className="w-4 h-4 text-gray-600 dark:text-gray-400 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M11.42 15.17 17.25 21A2.652 2.652 0 0 0 21 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 1 1-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 0 0 4.486-6.336l-3.276 3.277a3.004 3.004 0 0 1-2.25-2.25l3.276-3.276a4.5 4.5 0 0 0-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437 1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008Z"
                />
              </svg>
              {/* Tool Name */}
              <span className="font-medium text-sm text-gray-900 dark:text-gray-200 truncate">{toolCall.tool_name}</span>
              {/* Status Icon */}
              {getStatusIcon()}
              {status === 'running' && (
                <span className="text-xs text-blue-600 dark:text-blue-400">Running...</span>
              )}
              {/* Called Timestamp */}
              <span className="text-xs text-gray-600 dark:text-gray-500 select-none">{formatTimestamp(toolCall.timestamp)}</span>
            </div>
            {/* Expand/Collapse Chevron */}
            <svg
              className={`w-4 h-4 text-gray-600 dark:text-gray-400 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>

          {/* Expanded Details */}
          {isExpanded && (
            <div className="border-t border-gray-300 dark:border-gray-600 select-text" onClick={(e) => e.stopPropagation()}>
              {/* Tool Arguments */}
              {hasArguments && (
                <div className="px-4 py-3 bg-gray-100 dark:bg-gray-800/50">
                  <div className="text-xs font-medium text-gray-700 dark:text-gray-400 select-none mb-2">Arguments:</div>
                  <pre className="text-xs text-gray-900 dark:text-gray-300 overflow-x-auto bg-white dark:bg-gray-900 rounded p-2 font-mono border border-gray-300 dark:border-gray-700 select-text cursor-text">
                    {JSON.stringify(toolCall.tool_args, null, 2)}
                  </pre>
                </div>
              )}

              {/* Tool Result */}
              {hasResult && (() => {
                // Calculate duration between tool call and result
                const startTime = new Date(toolCall.timestamp).getTime()
                const endTime = new Date(toolResult.timestamp).getTime()
                const duration = endTime - startTime

                return (
                  <div className={`px-4 py-3 border-t ${isError ? 'border-red-300 dark:border-red-800 bg-red-100 dark:bg-red-900/10' : 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/30'}`}>
                    <div className="flex justify-between items-center mb-2">
                      <div className={`text-xs font-medium select-none ${isError ? 'text-red-700 dark:text-red-400' : 'text-green-700 dark:text-green-400'}`}>
                        {isError ? 'Error:' : 'Result:'}
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-500 select-none">
                        Returned: {formatTimestamp(toolResult.timestamp)} ({formatDuration(duration)})
                      </div>
                    </div>
                    <div className={`text-sm ${isError ? 'text-red-800 dark:text-red-300' : 'text-gray-900 dark:text-gray-300'} whitespace-pre-wrap font-mono max-h-96 overflow-y-auto select-text cursor-text`}>
                      {toolResult.result_content}
                    </div>
                  </div>
                )
              })()}
            </div>
          )}
        </button>
      </div>
    </div>
  )
}
