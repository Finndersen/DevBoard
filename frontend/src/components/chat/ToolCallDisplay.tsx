import { useState, useMemo, useCallback } from 'react'
import { ChatBubbleLeftRightIcon } from '@heroicons/react/24/outline'

import type { ToolCall, ToolResult } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { formatDuration, formatEventTiming } from '../../styles/messageStyles'
import { getToolDisplayLabel, formatToolDisplayLabel } from '../../utils/toolDisplayLabels'

import SubAgentConversationModal from '../claude-code/SubAgentConversationModal'

import { getRichResultRenderer, tryParseToolResult, getCustomToolDisplay } from './toolResultRenderers'

interface ToolCallDisplayProps {
  toolCall: ToolCall
  toolResult?: ToolResult
  isHighlighted?: boolean
  codebaseLocalPath?: string
  sessionId?: string
  previousEventTimestamp?: string | null
}

function StandardToolCallDisplay({ toolCall, toolResult, isHighlighted = false, codebaseLocalPath, sessionId, previousEventTimestamp }: ToolCallDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isSubAgentModalOpen, setIsSubAgentModalOpen] = useState(false)
  const hasResult = toolResult !== undefined
  const isError = toolResult?.is_error || false
  const hasArguments = toolCall.tool_args && Object.keys(toolCall.tool_args).length > 0

  // Compute display label with relevant context from tool arguments
  const displayLabel = useMemo(() => {
    return getToolDisplayLabel(
      toolCall.tool_name,
      toolCall.tool_args as Record<string, unknown> | null,
      codebaseLocalPath
    )
  }, [toolCall.tool_name, toolCall.tool_args, codebaseLocalPath])

  // Extract agentId from Task tool results (Claude Code native sub-agents)
  const subAgentInfo = useMemo(() => {
    if ((toolCall.tool_name !== 'Task' && toolCall.tool_name !== 'Agent') || !sessionId || !toolResult?.result_content) return null
    const match = toolResult.result_content.match(/agentId:\s*(\S+)/)
    if (!match) return null
    const args = toolCall.tool_args as Record<string, unknown> | null
    const description = args?.description as string | undefined
    const subagentType = args?.subagent_type as string | undefined
    return { agentId: match[1], description: description ?? 'Sub-agent conversation', subagentType }
  }, [toolCall.tool_name, toolCall.tool_args, toolResult?.result_content, sessionId])

  // Extract conversation_id from DevBoard sub-agent tool results (investigate_codebase / review_code_changes)
  const devboardSubAgentInfo = useMemo(() => {
    if (!['investigate_codebase', 'review_code_changes', 'execute_implementation_step'].includes(toolCall.tool_name) || !toolResult?.result_content) return null
    try {
      const data = JSON.parse(toolResult.result_content)
      if (typeof data.conversation_id !== 'number') return null
      return {
        conversationId: data.conversation_id as number,
        description: toolCall.tool_name === 'investigate_codebase'
          ? 'Investigation'
          : toolCall.tool_name === 'review_code_changes'
            ? 'Code Review'
            : 'Step Execution',
      }
    } catch {
      return null
    }
  }, [toolCall.tool_name, toolResult?.result_content])

  // Has any kind of sub-agent conversation to show
  const hasSubAgentConversation = subAgentInfo !== null || devboardSubAgentInfo !== null

  // Execution duration for the collapsed header timing badge
  const execDurationText = hasResult
    ? formatDuration(new Date(toolResult!.timestamp).getTime() - new Date(toolCall.timestamp).getTime())
    : null
  const timingText = previousEventTimestamp ? formatEventTiming(toolCall.timestamp, previousEventTimestamp) : null

  // Build fetchMessages callback for the modal
  const fetchMessages = useCallback(() => {
    if (subAgentInfo) {
      return apiClient.getClaudeCodeSubAgentMessages(sessionId!, subAgentInfo.agentId)
    }
    return apiClient.getConversationMessages(devboardSubAgentInfo!.conversationId)
  }, [subAgentInfo, devboardSubAgentInfo, sessionId])

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

  return (
    <div className="flex w-full min-w-0">
      {/* Collapsed Tool Call Card */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setIsExpanded(!isExpanded)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setIsExpanded(!isExpanded) } }}
        className={`group rounded-md overflow-hidden max-w-full min-w-[300px] text-left bg-gray-50 dark:bg-white/[0.03] border border-gray-200 dark:border-white/[0.06] hover:bg-gray-100 dark:hover:bg-white/[0.06] transition-colors cursor-pointer ${isHighlighted ? 'ring-2 ring-amber-400 dark:ring-amber-500' : ''}`}
      >
        {/* Minimal Header */}
        <div className="px-3 py-1.5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            {/* Tool Icon */}
            <svg
              className="w-4 h-4 text-gray-400 dark:text-gray-500 flex-shrink-0"
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
            {/* Tool Name and Details */}
            <span
              className="text-xs text-gray-900 dark:text-gray-200 truncate overflow-hidden text-ellipsis whitespace-nowrap"
              title={formatToolDisplayLabel(displayLabel)}
            >
              <span className="font-medium">{displayLabel.toolName}</span>
              {displayLabel.details && (
                <span className="font-normal italic text-gray-600 dark:text-gray-400">: {displayLabel.details}</span>
              )}
            </span>
            {/* Status Icon */}
            {getStatusIcon()}
            {status === 'running' && (
              <span className="text-xs text-blue-600 dark:text-blue-400">Running...</span>
            )}
            {/* View sub-agent conversation button */}
            {hasSubAgentConversation && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setIsSubAgentModalOpen(true) }}
                className="flex-shrink-0 p-0.5 rounded text-blue-500 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
                title="View sub-agent conversation"
              >
                <ChatBubbleLeftRightIcon className="w-4 h-4" />
              </button>
            )}
          </div>
          {/* Timing badge: HH:MM · +Xs (hover-reveal) · exec_duration (always) */}
          {(timingText || execDurationText) && (
            <div className="flex-shrink-0 text-[10px] text-gray-600 whitespace-nowrap flex items-center">
              {timingText && (
                <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                  {timingText}{execDurationText ? ' · ' : ''}
                </span>
              )}
              {execDurationText && <span>{execDurationText}</span>}
            </div>
          )}
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
            <div className="border-t border-gray-300 dark:border-white/[0.08] select-text min-w-0" onClick={(e) => e.stopPropagation()}>
              {/* Tool Arguments */}
              {hasArguments && (
                <div className="px-3 py-2 bg-gray-100 dark:bg-white/[0.05]">
                  <div className="text-xs font-medium text-gray-700 dark:text-gray-400 select-none mb-1.5">Arguments:</div>
                  <pre className="text-xs text-gray-900 dark:text-gray-300 bg-white dark:bg-gray-900 rounded p-2 font-mono border border-gray-300 dark:border-white/[0.08] select-text cursor-text whitespace-pre overflow-x-auto">
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

                // Try to render with a rich renderer if available
                const RichRenderer = !isError ? getRichResultRenderer(toolCall.tool_name) : null
                const parsedData = RichRenderer ? tryParseToolResult(toolResult.result_content) : null

                return (
                  <div className={`px-3 py-2 border-t min-w-0 ${isError ? 'border-red-300 dark:border-red-800 bg-red-100 dark:bg-red-900/10' : 'border-gray-300 dark:border-white/[0.06] bg-gray-50 dark:bg-white/[0.03]'}`}>
                    <div className="flex justify-between items-center mb-1.5 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className={`text-xs font-medium select-none ${isError ? 'text-red-700 dark:text-red-400' : 'text-green-700 dark:text-green-400'}`}>
                          {isError ? 'Error:' : 'Result:'}
                        </div>
                        {parsedData !== null && (() => {
                          const d = parsedData as Record<string, unknown>
                          return <>
                            {d.step_type != null && (
                              <span className="text-[11px] text-gray-400 dark:text-gray-500 font-mono select-text">
                                type: {d.step_type as string}
                              </span>
                            )}
                            {d.step_type != null && d.conversation_id != null && (
                              <span className="text-[11px] text-gray-300 dark:text-gray-600 select-none">|</span>
                            )}
                            {d.conversation_id != null && (
                              <span className="text-[11px] text-gray-400 dark:text-gray-500 font-mono select-text">
                                conversation: {d.conversation_id as number}
                              </span>
                            )}
                          </>
                        })()}
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-500 select-none">
                        {formatDuration(duration)}
                      </div>
                    </div>
                    {RichRenderer && parsedData !== null ? (
                      <RichRenderer data={parsedData} toolCall={toolCall} />
                    ) : (
                      <div className={`text-xs ${isError ? 'text-red-800 dark:text-red-300' : 'text-gray-900 dark:text-gray-300'} whitespace-pre-wrap font-mono max-h-96 overflow-y-auto overflow-x-auto select-text cursor-text min-w-0`}>
                        {toolResult.result_content}
                      </div>
                    )}
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      {hasSubAgentConversation && (
        <SubAgentConversationModal
          isOpen={isSubAgentModalOpen}
          onClose={() => setIsSubAgentModalOpen(false)}
          fetchMessages={fetchMessages}
          title={subAgentInfo?.description ?? devboardSubAgentInfo!.description}
          subagentType={subAgentInfo?.subagentType ?? devboardSubAgentInfo?.description}
          subtitle={subAgentInfo?.agentId}
        />
      )}
    </div>
  )
}

export default function ToolCallDisplay({ toolCall, toolResult, isHighlighted = false, codebaseLocalPath, sessionId, previousEventTimestamp }: ToolCallDisplayProps) {
  const CustomDisplay = getCustomToolDisplay(toolCall.tool_name)
  if (CustomDisplay) {
    return <CustomDisplay toolCall={toolCall} toolResult={toolResult} />
  }

  return <StandardToolCallDisplay toolCall={toolCall} toolResult={toolResult} isHighlighted={isHighlighted} codebaseLocalPath={codebaseLocalPath} sessionId={sessionId} previousEventTimestamp={previousEventTimestamp} />
}
