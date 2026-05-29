import { useCallback, useEffect, useRef } from 'react'
import { useBackgroundAgentRun, useBackgroundAgent, useBackgroundAgentRunConversation } from '../hooks/useBackgroundAgents'
import { apiClient } from '../lib/api'
import { useUIStore } from '../stores/uiStore'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { useEventHandlerRegistryForStream } from '../hooks/useConversationEventHandlers'
import { ErrorMessage } from '../components/ui'
import { loadingSpinner, textColors, borderColors } from '../styles/designSystem'
import ConversationMessageList from '../components/chat/ConversationMessageList'
import {
  formatTriggeredBy,
  formatDuration,
  formatRelativeTime,
  statusBadgeClass,
} from './backgroundAgentUtils'
import type { BackgroundAgentRunStatus, ConversationEvent } from '../lib/api'

const EMPTY_MESSAGES: ConversationEvent[] = []

interface Props {
  id: string
}

function StatusBadge({ status, pulse }: { status: BackgroundAgentRunStatus; pulse?: boolean }) {
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${statusBadgeClass(status)} ${pulse ? 'animate-pulse' : ''}`}>
      {status}
    </span>
  )
}

export default function BackgroundAgentRunDetail({ id }: Props) {
  const navigateTo = useUIStore(state => state.navigateTo)

  const { data: run, loading: runLoading, error: runError } = useBackgroundAgentRun(id)
  const { data: agent } = useBackgroundAgent(run?.agent_id ?? null)
  const { data: conversation, loading: convLoading } = useBackgroundAgentRunConversation(id)

  const conversationId = conversation?.id ?? null

  // Store subscriptions (null-safe: conversationId may not be resolved yet)
  const messages = useConversationStreamStore(
    state => conversationId !== null
      ? (state.conversationMessages.get(conversationId)?.messages ?? EMPTY_MESSAGES)
      : EMPTY_MESSAGES
  )
  const historyLoaded = useConversationStreamStore(
    state => conversationId !== null
      ? (state.conversationMessages.get(conversationId)?.historyLoaded ?? false)
      : false
  )
  const isStreaming = useConversationStreamStore(
    state => conversationId !== null
      ? (state.activeStreams.get(conversationId)?.isStreaming ?? false)
      : false
  )
  const contextUsage = useConversationStreamStore(
    state => conversationId !== null
      ? state.conversationMessages.get(conversationId)?.contextUsage
      : undefined
  )

  const setMessages = useConversationStreamStore(state => state.setMessages)
  const reconnectStream = useConversationStreamStore(state => state.reconnectStream)
  const updateEventHandlerRegistry = useConversationStreamStore(state => state.updateEventHandlerRegistry)
  const eventHandlerRegistry = useEventHandlerRegistryForStream()

  // Register event handler registry so streaming events are dispatched correctly
  useEffect(() => {
    if (conversationId !== null) {
      updateEventHandlerRegistry(conversationId, eventHandlerRegistry)
    }
  }, [conversationId, eventHandlerRegistry, updateEventHandlerRegistry])

  // Seed history once per conversationId, then reconnect if an execution is still active
  const historyFetchedRef = useRef<number | null>(null)
  useEffect(() => {
    if (conversationId === null || historyLoaded) return
    if (historyFetchedRef.current === conversationId) return
    historyFetchedRef.current = conversationId

    const load = async () => {
      try {
        const { messages: data, context_usage } = await apiClient.getConversationMessages(conversationId)
        setMessages(conversationId, data, context_usage)
      } catch {
        setMessages(conversationId, [])
      }
      try {
        const hasActive = await apiClient.hasActiveExecution(conversationId)
        if (hasActive && !useConversationStreamStore.getState().isConversationStreaming(conversationId)) {
          reconnectStream(conversationId)
        }
      } catch {
        // Silently ignore
      }
    }
    load()
  }, [conversationId, historyLoaded, setMessages, reconnectStream])

  const handleBack = useCallback(() => {
    if (run) {
      navigateTo({ type: 'background-agent-detail', entityId: String(run.agent_id), title: agent?.name ?? 'Agent' })
    } else {
      navigateTo({ type: 'background-agents-list', entityId: '', title: 'Agents' })
    }
  }, [navigateTo, run, agent])

  if (runLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className={loadingSpinner} />
      </div>
    )
  }

  if (runError || !run) {
    return (
      <div className="p-6">
        <ErrorMessage error={runError ? String(runError) : 'Run not found'} />
      </div>
    )
  }

  const { icon: triggerIcon, label: triggerLabel } = formatTriggeredBy(run.triggered_by)
  const duration = formatDuration(run.started_at, run.completed_at)
  const startedAt = formatRelativeTime(run.started_at)
  const isLoadingContent = convLoading || (conversationId !== null && !historyLoaded)

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className={`flex items-center justify-between px-6 py-4 border-b ${borderColors.default} flex-shrink-0`}>
        <div className="flex items-center gap-3">
          <button
            onClick={handleBack}
            className="text-gray-500 hover:text-gray-300 transition-colors text-sm"
            aria-label="Back to agent"
          >
            ← {agent?.name ?? 'Agent'}
          </button>
          <h1 className={`text-lg font-semibold ${textColors.primary}`}>Run Conversation</h1>
        </div>
      </div>

      {/* Run metadata bar */}
      <div
        className={`flex items-center gap-4 px-6 py-3 border-b bg-gray-800/50 text-xs text-gray-400 flex-shrink-0 ${borderColors.default}`}
        data-testid="run-meta-bar"
      >
        <StatusBadge status={run.status} pulse={isStreaming} />
        <span>
          {triggerIcon} {triggerLabel} — {startedAt}
        </span>
        {run.completed_at && (
          <span>Duration: {duration}</span>
        )}
        {(run.input_tokens != null || run.output_tokens != null) && (
          <span>
            Tokens: {run.input_tokens ?? 0} in · {run.output_tokens ?? 0} out
          </span>
        )}
        {run.status === 'failed' && run.error && (
          <span className="text-red-400">✕ {run.error}</span>
        )}
      </div>

      {/* Conversation transcript */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isLoadingContent ? (
          <div className="flex items-center justify-center py-12">
            <div className={loadingSpinner} />
          </div>
        ) : (
          <>
            <ConversationMessageList
              messages={messages}
              pendingMessage={null}
              onRetryMessage={() => {}}
              emptyStateMessage="No messages in this run"
              showEmptyState={messages.length === 0 && !isStreaming}
            />
            {isStreaming && (
              <div className="flex items-center gap-1 mt-3 px-1" aria-label="Agent is streaming">
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse [animation-delay:300ms]" />
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer: live streaming indicator */}
      {isStreaming && (
        <div
          className={`flex items-center gap-3 px-6 py-2 border-t ${borderColors.default} text-xs flex-shrink-0`}
          data-testid="streaming-footer"
        >
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            <span className="text-green-400 font-medium">Streaming live</span>
          </div>
          {contextUsage != null && (
            <span className="text-gray-400">
              {contextUsage.input_tokens + contextUsage.output_tokens} tokens
            </span>
          )}
        </div>
      )}
    </div>
  )
}
