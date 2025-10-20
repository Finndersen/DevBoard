import type { ConversationEvent, ToolResult } from '../../lib/api'
import {
  getMessageAlignment,
  getMessageContainerAlignment,
  getMessageBubbleClasses,
  getTimestampClasses,
  formatTimestamp
} from '../../styles/messageStyles'
import { Markdown } from '../ui'
import ToolCallDisplay from './ToolCallDisplay'

interface ConversationMessageProps {
  message: ConversationEvent
  // Optional: pass the corresponding tool result for a tool call
  toolResult?: ToolResult
}

export default function ConversationMessageComponent({ message, toolResult }: ConversationMessageProps) {
  // Handle different event types
  if (message.event_type === 'message') {
    const isUser = message.role === 'user'

    return (
      <div className={`flex ${getMessageAlignment(isUser)}`}>
        <div className={`max-w-[80%] flex flex-col ${getMessageContainerAlignment(isUser)}`}>
          {/* Message bubble */}
          <div className={getMessageBubbleClasses(isUser)}>
            <Markdown forceWhiteText={isUser}>
              {message.text_content}
            </Markdown>

            {/* Timestamp */}
            <div className={`text-xs mt-1 opacity-70 ${getTimestampClasses(isUser)}`}>
              {formatTimestamp(message.timestamp)}
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
      <div className="flex justify-start my-2">
        <div className="max-w-[80%] flex flex-col items-start">
          <div className="rounded-lg border border-yellow-600 bg-yellow-900/10 overflow-hidden shadow-sm w-full">
            <div className="px-4 py-2 bg-yellow-800/20 border-b border-yellow-600 flex items-center gap-2">
              <svg
                className="w-4 h-4 text-yellow-400"
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
              <span className="font-medium text-sm text-yellow-200">Awaiting Approval: {message.tool_name}</span>
            </div>
            {message.tool_args && typeof message.tool_args === 'object' && Object.keys(message.tool_args).length > 0 && (
              <div className="px-4 py-3">
                <div className="text-xs font-medium text-gray-400 mb-2">Arguments:</div>
                <pre className="text-xs text-gray-300 overflow-x-auto bg-gray-900 rounded p-2 font-mono">
                  {typeof message.tool_args === 'string'
                    ? message.tool_args
                    : JSON.stringify(message.tool_args, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // Fallback for unknown event types
  return null
}