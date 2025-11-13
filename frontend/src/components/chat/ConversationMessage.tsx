import { useState, useRef, useEffect } from 'react'
import type { ConversationEvent, ToolResult } from '../../lib/api'
import {
  getMessageBubbleClasses,
  formatTimestamp
} from '../../styles/messageStyles'
import { Markdown } from '../ui'
import ToolCallDisplay from './ToolCallDisplay'

interface ConversationMessageProps {
  message: ConversationEvent
  // Optional: pass the corresponding tool result for a tool call
  toolResult?: ToolResult
  // Whether this is the latest message (should not be collapsible)
  isLatest?: boolean
}

const MAX_COLLAPSED_HEIGHT = 240 // ~10 lines at typical line height

export default function ConversationMessageComponent({ message, toolResult, isLatest = false }: ConversationMessageProps) {
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
          {/* Show more/less button (centered) and timestamp (right-aligned) on same line */}
          <div className="flex justify-between items-center mt-1">
            <div className="flex-1"></div>
            {needsExpansion && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={`text-xs font-medium hover:underline flex-shrink-0 ${
                  isUser
                    ? 'text-blue-100 hover:text-white'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
              >
                {isExpanded ? '▲ Show less' : '▼ Show more'}
              </button>
            )}
            <div className="flex-1 flex justify-end">
              <div className={`text-xs ${isUser ? 'text-blue-200 dark:text-blue-300' : 'text-gray-500 dark:text-gray-400'}`}>
                {formatTimestamp(message.timestamp)}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (message.event_type === 'tool_call') {
    return <ToolCallDisplay toolCall={message} toolResult={toolResult} />
  }

  // Tool results are rendered as part of their corresponding tool call
  if (message.event_type === 'tool_result') {
    return null
  }

  // Tool call requests (pending approval) - render similarly to tool calls but with different styling
  if (message.event_type === 'tool_call_request') {
    return (
      <div className="flex w-full min-w-0">
        <div className="rounded-lg border border-yellow-600 bg-yellow-900/10 overflow-hidden shadow-sm max-w-full min-w-[300px]">
          <div className="px-3 py-1.5 bg-yellow-800/20 border-b border-yellow-600 flex items-center justify-between gap-2 min-w-0">
            <div className="flex items-center gap-2 min-w-0">
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
              <span className="font-medium text-sm text-yellow-200 truncate">Awaiting Approval: {message.tool_name}</span>
            </div>
            <div className="text-xs text-yellow-300/70 flex-shrink-0">
              {formatTimestamp(message.timestamp)}
            </div>
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

  // System events - ignore for now (will add event-specific handling later)
  if (message.event_type === 'system') {
    return null
  }

  // Fallback for unknown event types
  return null
}