import { memo, useState, useEffect, useMemo } from 'react'

import type { ToolCall, ToolResult } from '../../lib/api'
import { cleanToolName } from '../../utils/toolDisplayLabels'
import ToolCallDisplay from './ToolCallDisplay'

interface ToolCallGroupDisplayProps {
  items: Array<{ message: ToolCall; index: number }>
  toolResultMap: Map<string, ToolResult>
  highlightSet: Set<string>
  codebaseLocalPath?: string
}

function ToolCallGroupDisplay({ items, toolResultMap, highlightSet, codebaseLocalPath }: ToolCallGroupDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  // Auto-expand if any item in the group is highlighted
  useEffect(() => {
    const hasHighlight = items.some(({ message }) => {
      const uuid = (message as { uuid?: string }).uuid
      return uuid ? highlightSet.has(uuid) : false
    })
    if (hasHighlight) {
      setIsExpanded(true)
    }
  }, [items, highlightSet])

  // Compute summary string, e.g. "Read (3), Bash (2)"
  const summaryText = useMemo(() => {
    const counts = new Map<string, number>()
    for (const { message } of items) {
      const name = cleanToolName(message.tool_name)
      counts.set(name, (counts.get(name) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([name, count]) => (count > 1 ? `${name} (${count})` : name))
      .join(', ')
  }, [items])

  const resultCounts = useMemo(() => {
    let succeeded = 0
    let failed = 0
    for (const { message, index } of items) {
      const cacheKey = `${message.timestamp}-tool_call-${index}`
      const result = toolResultMap.get(cacheKey)
      if (result) {
        result.is_error ? failed++ : succeeded++
      }
    }
    return { succeeded, failed }
  }, [items, toolResultMap])

  // Aggregate status across all tool calls in the group
  const status = useMemo(() => {
    let allHaveResults = true
    let anyError = false

    for (const { message, index } of items) {
      const cacheKey = `${message.timestamp}-tool_call-${index}`
      const result = toolResultMap.get(cacheKey)
      if (!result) {
        allHaveResults = false
      } else if (result.is_error) {
        anyError = true
      }
    }

    if (!allHaveResults) return 'running'
    if (anyError) return 'error'
    return 'complete'
  }, [items, toolResultMap])

  const isHighlighted = items.some(({ message }) => {
    const uuid = (message as { uuid?: string }).uuid
    return uuid ? highlightSet.has(uuid) : false
  })

  const statusIcon = () => {
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

  return (
    <div className="flex flex-col w-full min-w-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={`rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/30 overflow-hidden shadow-sm max-w-full min-w-[300px] text-left hover:opacity-80 transition-opacity ${isHighlighted ? 'ring-2 ring-amber-400 dark:ring-amber-500' : ''}`}
      >
        <div className="px-3 py-1.5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            {/* Wrench icon */}
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
            {/* Summary text */}
            <span className="text-sm font-semibold text-gray-900 dark:text-gray-200 truncate overflow-hidden text-ellipsis whitespace-nowrap">
              {summaryText}
            </span>
            {/* Status icon */}
            {statusIcon()}
            {/* Count badge */}
            <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
              {items.length} tool calls
              {status !== 'running' && resultCounts.failed > 0 && (
                <> · <span className="text-red-600 dark:text-red-400">({resultCounts.failed} failed)</span></>
              )}
            </span>
          </div>
          {/* Chevron */}
          <svg
            className={`w-4 h-4 text-gray-600 dark:text-gray-400 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded individual tool calls */}
      {isExpanded && (
        <div className="space-y-1 mt-1 ml-3 pl-3 border-l-2 border-gray-200 dark:border-gray-700">
          {items.map(({ message, index }) => {
            const cacheKey = `${message.timestamp}-tool_call-${index}`
            const toolResult = toolResultMap.get(cacheKey)
            const uuid = (message as { uuid?: string }).uuid
            const isItemHighlighted = uuid ? highlightSet.has(uuid) : false

            return (
              <div key={cacheKey} id={uuid ? `msg-${uuid}` : undefined}>
                <ToolCallDisplay
                  toolCall={message}
                  toolResult={toolResult}
                  isHighlighted={isItemHighlighted}
                  codebaseLocalPath={codebaseLocalPath}
                />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default memo(ToolCallGroupDisplay)
