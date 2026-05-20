import { useCallback } from 'react'
import type { ReactNode } from 'react'
import ConversationModelSelector from '../chat/ConversationModelSelector'
import ConversationInput from '../chat/ConversationInput'
import { surfaces, borderColors, textColors } from '../../styles/designSystem'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useSendConversationMessage } from '../../hooks/useSendConversationMessage'
import { useViewContext } from '../../contexts/ViewContext'
import { useApprovals } from '../../stores/approvalsStore'
import { createConversationApprovalKey } from '../../utils/approvalKeys'
import { useMessageQueueing } from '../chat/hooks/useMessageQueueing'

interface AgentActionBarProps {
  conversationId: number | null
  isRunningAction?: boolean
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
  isRunningAction = false,
  isStreaming,
  onStopStream,
  isDisabled,
  disabledMessage = "Chat is disabled",
  placeholder = "Message the agent...",
  workflowActions,
  onModelChange,
}: AgentActionBarProps) {
  const isQueued = useConversationStreamStore(
    state => conversationId ? (state.activeStreams.get(conversationId)?.isQueued ?? false) : false
  )
  const isStopping = useConversationStreamStore(
    state => conversationId ? (state.activeStreams.get(conversationId)?.isStopping ?? false) : false
  )
  const setQueued = useConversationStreamStore(state => state.setQueued)

  const { sendMessage: sendMessageViaHook } = useSendConversationMessage({
    conversationId: conversationId ?? 0
  })

  const { viewType, entityId } = useViewContext()

  const pendingApprovals = useApprovals(
    conversationId ? createConversationApprovalKey(conversationId) : ''
  )

  const { inputMessage, setInputMessage, handleSendMessage } = useMessageQueueing(
    conversationId ?? 0,
    isStreaming,
    pendingApprovals,
    isRunningAction,
    isQueued,
    setQueued,
    sendMessageViaHook,
    viewType,
    entityId
  )

  const handleSend = useCallback(() => {
    handleSendMessage()
  }, [handleSendMessage])

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
              dropUp
            />
          </div>
        )}

        {/* Chat input */}
        <div className="flex-1 min-w-0">
          <ConversationInput
            value={inputMessage}
            onChange={setInputMessage}
            onSendMessage={handleSend}
            placeholder={placeholder}
            isStreaming={isStreaming}
            onStopStream={onStopStream}
            isQueued={isQueued}
            isStopping={isStopping}
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
