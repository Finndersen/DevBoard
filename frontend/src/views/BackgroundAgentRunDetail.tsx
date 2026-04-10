import { useCallback } from 'react'
import { useBackgroundAgentRun, useBackgroundAgent, useBackgroundAgentRunConversation } from '../hooks/useBackgroundAgents'
import { useApi } from '../hooks/useApi'
import { apiClient } from '../lib/api'
import { useUIStore } from '../stores/uiStore'
import { ErrorMessage } from '../components/ui'
import { loadingSpinner, textColors, borderColors } from '../styles/designSystem'
import ConversationMessageList from '../components/chat/ConversationMessageList'
import {
  formatTriggeredBy,
  formatDuration,
  formatRelativeTime,
  statusBadgeClass,
} from './backgroundAgentUtils'
import type { BackgroundAgentRunStatus } from '../lib/api'

interface Props {
  id: string
}

function StatusBadge({ status }: { status: BackgroundAgentRunStatus }) {
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${statusBadgeClass(status)}`}>
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
  const { data: messagesResponse, loading: messagesLoading } = useApi(
    () => apiClient.getConversationMessages(conversationId!),
    { immediate: conversationId !== null }
  )

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
  const messages = messagesResponse?.messages ?? []
  const isLoadingContent = convLoading || messagesLoading

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
        <StatusBadge status={run.status} />
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
          <ConversationMessageList
            messages={messages}
            pendingMessage={null}
            onRetryMessage={() => {}}
            emptyStateMessage="No messages in this run"
            showEmptyState={messages.length === 0}
          />
        )}
      </div>
    </div>
  )
}
