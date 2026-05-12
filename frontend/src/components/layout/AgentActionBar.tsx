import { useState, useCallback, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import ConversationModelSelector from '../chat/ConversationModelSelector'
import ConversationInput from '../chat/ConversationInput'
import { surfaces, borderColors, textColors } from '../../styles/designSystem'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

interface AgentActionBarProps {
  conversationId: number | null
  onSendMessage: (text: string) => void
  isStreaming: boolean
  onStopStream: () => void
  isDisabled: boolean
  disabledMessage?: string
  placeholder?: string
  workflowActions?: ReactNode
  onModelChange?: (engine: string, modelId: string | null, modelName: string) => void
}

export default function AgentActionBar({
  conversationId,
  onSendMessage,
  isStreaming,
  onStopStream,
  isDisabled,
  disabledMessage = "Chat is disabled",
  placeholder = "Message the agent...",
  workflowActions,
  onModelChange
}: AgentActionBarProps) {
  const [inputMessage, setInputMessage] = useState('')

  const isQueued = useConversationStreamStore(
    state => conversationId ? (state.activeStreams.get(conversationId)?.isQueued ?? false) : false
  )
  const setQueued = useConversationStreamStore(state => state.setQueued)

  // Clear input when queued message is auto-sent (isQueued transitions true → false)
  const prevQueuedRef = useRef(false)
  useEffect(() => {
    if (prevQueuedRef.current && !isQueued) {
      setInputMessage('')
    }
    prevQueuedRef.current = isQueued
  }, [isQueued])

  // Unqueue when user edits input while queued
  const handleInputChange = useCallback((text: string) => {
    setInputMessage(text)
    if (isQueued && conversationId) {
      setQueued(conversationId, false)
    }
  }, [isQueued, conversationId, setQueued])

  const handleSend = useCallback(() => {
    const text = inputMessage.trim()
    if (!text) return
    onSendMessage(text)
    // Clear input immediately for non-queued sends; keep text visible when queued
    if (!isStreaming) {
      setInputMessage('')
    }
  }, [inputMessage, onSendMessage, isStreaming])

  if (isDisabled) {
    return (
      <div className={`border ${borderColors.default} ${surfaces.raised} p-3 rounded-lg`}>
        <div className={`text-center ${textColors.muted} text-sm`}>
          {disabledMessage}
        </div>
      </div>
    )
  }

  return (
    <div className={`border ${borderColors.default} ${surfaces.raised} p-2 rounded-lg`}>
      <div className="flex items-center gap-2">
        {/* Streaming indicator — just the pulsing dot, verbose label is in the chat header */}
        {isStreaming && (
          <div className="relative w-2.5 h-2.5 flex-shrink-0" title="Agent working...">
            <div className="absolute inset-0 bg-green-500 rounded-full animate-ping opacity-40"></div>
            <div className="w-2.5 h-2.5 bg-green-500 rounded-full"></div>
          </div>
        )}

        {/* Model selector - dimmed while streaming */}
        {conversationId !== null && (
          <div className={`flex-shrink-0 ${isStreaming ? 'opacity-50 pointer-events-none' : ''}`}>
            <ConversationModelSelector
              conversationId={conversationId}
              onModelChange={onModelChange}
              showEngine={false}
              dropUp
            />
          </div>
        )}

        {/* Chat input */}
        <div className="flex-1 min-w-0">
          <ConversationInput
            value={inputMessage}
            onChange={handleInputChange}
            onSendMessage={handleSend}
            placeholder={placeholder}
            isStreaming={isStreaming}
            onStopStream={onStopStream}
            isQueued={isQueued}
          />
        </div>

        {/* Optional divider before workflow actions */}
        {workflowActions && (
          <div className="w-px h-6 bg-gray-600 flex-shrink-0"></div>
        )}

        {/* Optional workflow action buttons */}
        {workflowActions && (
          <div className="flex-shrink-0">
            {workflowActions}
          </div>
        )}
      </div>
    </div>
  )
}