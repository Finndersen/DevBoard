import { useState, useRef, useEffect, useMemo } from 'react'
import type { ConversationEvent, ToolResult, SystemEventType } from '../../lib/api'
import {
  getMessageBubbleClasses
} from '../../styles/messageStyles'
import { Markdown } from '../ui'
import ToolCallDisplay from './ToolCallDisplay'
import { getToolDisplayLabel, formatToolDisplayLabel } from '../../utils/toolDisplayLabels'

function getSystemEventLabel(type: SystemEventType): string | null {
  switch (type) {
    case 'workspace_create':
      return 'Creating workspace'
    default:
      return null
  }
}

interface ConversationMessageProps {
  message: ConversationEvent
  // Optional: pass the corresponding tool result for a tool call
  toolResult?: ToolResult
  // Whether this is the latest message (should not be collapsible)
  isLatest?: boolean
  // Optional codebase local path for relativizing file paths in tool display labels
  codebaseLocalPath?: string
}

const MAX_COLLAPSED_HEIGHT = 240 // ~10 lines at typical line height

export default function ConversationMessageComponent({ message, toolResult, isLatest = false, codebaseLocalPath }: ConversationMessageProps) {
  // Handle different event types
  if (message.event_type === 'message') {
    const isUser = message.role === 'user'
    const [isExpanded, setIsExpanded] = useState(false)
    const [needsExpansion, setNeedsExpansion] = useState(false)
    const contentRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
      // Don't check for expansion if this is the latest message
      if (isLatest || !contentRef.current) {
        setNeedsExpansion(false)
        return
      }

      const height = contentRef.current.scrollHeight
      setNeedsExpansion(height > MAX_COLLAPSED_HEIGHT)
    }, [message.text_content, isLatest])

    return (
      <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
        {/* Message bubble with content-based width */}
        <div className={`${getMessageBubbleClasses(isUser)} max-w-full min-w-[200px]`}>
          <div className="relative">
            <div
              ref={contentRef}
              className={`overflow-hidden transition-all duration-300 ${
                !isExpanded && needsExpansion ? 'max-h-60' : ''
              }`}
              style={{
                maxHeight: !isExpanded && needsExpansion ? `${MAX_COLLAPSED_HEIGHT}px` : undefined
              }}
            >
              <Markdown forceWhiteText={isUser}>
                {message.text_content}
              </Markdown>
            </div>
            {/* Fade overlay when collapsed */}
            {needsExpansion && !isExpanded && (
              <div
                className={`absolute bottom-0 left-0 right-0 h-16 pointer-events-none ${
                  isUser
                    ? 'bg-gradient-to-t from-blue-600 to-transparent'
                    : 'bg-gradient-to-t from-gray-100 dark:from-gray-700 to-transparent'
                }`}
              />
            )}
          </div>
          {/* Show more/less button (centered) */}
          {needsExpansion && (
            <div className="flex justify-center mt-1">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={`text-xs font-medium hover:underline ${
                  isUser
                    ? 'text-blue-100 hover:text-white'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
              >
                {isExpanded ? '▲ Show less' : '▼ Show more'}
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (message.event_type === 'tool_call') {
    return <ToolCallDisplay toolCall={message} toolResult={toolResult} codebaseLocalPath={codebaseLocalPath} />
  }

  // Tool results are rendered as part of their corresponding tool call
  if (message.event_type === 'tool_result') {
    return null
  }

  // Tool call requests (pending approval) - render similarly to tool calls but with different styling
  if (message.event_type === 'tool_call_request') {
    // Compute display label for the tool request (tool_args can be string | object | null)
    const toolArgs = typeof message.tool_args === 'object' ? message.tool_args : null
    const displayLabel = getToolDisplayLabel(message.tool_name, toolArgs, codebaseLocalPath)

    return (
      <div className="flex w-full min-w-0">
        <div className="rounded-lg border border-yellow-600 bg-yellow-900/10 overflow-hidden shadow-sm max-w-full min-w-[300px]">
          <div className="px-3 py-1.5 bg-yellow-800/20 border-b border-yellow-600 flex items-center gap-2 min-w-0">
            <svg
              className="w-4 h-4 text-yellow-400 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span
              className="text-sm text-yellow-200 truncate overflow-hidden text-ellipsis whitespace-nowrap"
              title={`Awaiting Approval: ${formatToolDisplayLabel(displayLabel)}`}
            >
              <span className="font-normal">Awaiting Approval: </span>
              <span className="font-semibold">{displayLabel.toolName}</span>
              {displayLabel.details && (
                <span className="font-normal italic text-yellow-300/80">: {displayLabel.details}</span>
              )}
            </span>
          </div>
          {message.tool_args && typeof message.tool_args === 'object' && Object.keys(message.tool_args).length > 0 && (
            <div className="px-3 py-2">
              <div className="text-xs font-medium text-gray-400 mb-2">Arguments:</div>
              <pre className="text-xs text-gray-300 bg-gray-900 rounded p-2 font-mono whitespace-pre overflow-x-auto">
                {typeof message.tool_args === 'string'
                  ? message.tool_args
                  : JSON.stringify(message.tool_args, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    )
  }

  // System events - render as inline badges (only for specific event types)
  if (message.event_type === 'system') {
    const label = getSystemEventLabel(message.type)

    // Only render badge if we have a label for this event type
    if (!label) {
      return null
    }

    return (
      <div className="flex w-full justify-center my-1">
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-xs text-blue-400">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <span>{label}</span>
        </div>
      </div>
    )
  }

  // Fallback for unknown event types
  return null
}