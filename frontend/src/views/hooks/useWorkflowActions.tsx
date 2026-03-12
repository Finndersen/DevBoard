import { useState, useCallback } from 'react'
import type { Task, GitHubPRStatusResponse } from '../../lib/api'
import { apiClient } from '../../lib/api'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { Button } from '../../components/ui'

const WORKFLOW_ACTION_LABELS: Record<string, string> = {
  'task.create_implementation_plan': 'Generate a technical implementation plan from the task specification',
  'task.start_implementation': 'Start implementing the approved plan',
  'task.rebase_branch': 'Rebase task branch onto base branch',
  'task.approve_and_merge': 'Approve changes and merge locally',
  'task.approve_and_create_pr': 'Approve changes and create PR',
  'task.merge_and_finalise': 'Merge PR and complete task',
  'task.complete_no_merge': 'Complete task (no merge)',
}

interface UseWorkflowActionsParams {
  task: Task | null
  prStatus: GitHubPRStatusResponse | null
  specificationContent: string | undefined
  refetch: () => Promise<void>
}

interface UseWorkflowActionsResult {
  streamingMessage: string
  setStreamingMessage: (message: string) => void
  executeWorkflowAction: (actionKey: string, message: string) => Promise<void>
  getWorkflowActionButtons: () => React.ReactElement | null
  handleTriggerRebase: () => void
}

export function useWorkflowActions({ task, prStatus, specificationContent, refetch }: UseWorkflowActionsParams): UseWorkflowActionsResult {
  const [streamingMessage, setStreamingMessage] = useState('')

  const reconnectStream = useConversationStreamStore(state => state.reconnectStream)
  const isConversationStreaming = useConversationStreamStore(
    state => task?.conversation_id ? state.isConversationStreaming(task.conversation_id) : false
  )

  const executeWorkflowAction = useCallback(async (actionKey: string, message: string) => {
    if (!task?.id) return

    setStreamingMessage(message)
    try {
      const result = await apiClient.executeWorkflowAction(task.id, { action_key: actionKey })

      // Refetch task details first — conversation_id may have changed.
      await refetch()

      if (result.conversation_id) {
        // Explicitly open WebSocket — needed when action reuses the same conversation,
        // as useStreamSubscription's reconnectAttempted guard won't re-trigger.
        reconnectStream(result.conversation_id)
      } else {
        setStreamingMessage('')
      }
    } catch (error) {
      console.error('Failed to execute workflow action:', error)
      setStreamingMessage('')
      await refetch()
    }
  }, [task?.id, refetch, reconnectStream])

  const getButtonConfigForAction = (actionKey: string) => {
    const configs: Record<string, { loadingMessage: string; className?: string; isDisabled?: () => boolean }> = {
      'task.create_implementation_plan': {
        loadingMessage: 'Generating Implementation Plan...',
        isDisabled: () => !specificationContent || specificationContent.trim() === '',
      },
      'task.begin_implementation': {
        loadingMessage: 'Starting Implementation...',
        className: 'bg-green-600 hover:bg-green-700 focus:ring-green-500',
      },
      'task.approve_and_merge': {
        loadingMessage: 'Merging changes...',
        className: 'bg-green-600 hover:bg-green-700 focus:ring-green-500',
      },
      'task.approve_and_create_pr': {
        loadingMessage: 'Creating Pull Request...',
      },
      'task.merge_and_finalise': {
        loadingMessage: 'Merging PR and completing...',
        className: 'bg-green-600 hover:bg-green-700 focus:ring-green-500',
        isDisabled: () => prStatus !== null && !prStatus.merged && prStatus.mergeable_state !== 'CLEAN',
      },
      'task.finalise': {
        loadingMessage: 'Completing task...',
      },
    }
    return configs[actionKey] || { loadingMessage: 'Processing...' }
  }

  const getWorkflowActionButtons = useCallback((): React.ReactElement | null => {
    if (!task?.available_workflow_actions?.length) return null

    const actionsToShow = task.available_workflow_actions.filter(
      action => action.key !== 'task.rebase_branch'
    )

    if (actionsToShow.length === 0) return null

    return (
      <div className="flex gap-2">
        {actionsToShow.map(action => {
          const config = getButtonConfigForAction(action.key)
          const isDisabled = isConversationStreaming || (config.isDisabled?.() ?? false)

          return (
            <Button
              key={action.key}
              onClick={() => executeWorkflowAction(action.key, config.loadingMessage)}
              variant="primary"
              className={config.className}
              disabled={isDisabled}
            >
              {action.key === 'task.merge_and_finalise' && prStatus?.merged
                ? 'Complete task'
                : (WORKFLOW_ACTION_LABELS[action.key] ?? action.key)}
            </Button>
          )
        })}
      </div>
    )
  }, [task?.available_workflow_actions, isConversationStreaming, executeWorkflowAction, prStatus, specificationContent])

  const handleTriggerRebase = useCallback(() => {
    executeWorkflowAction('task.rebase_branch', 'Rebasing branch...')
  }, [executeWorkflowAction])

  return {
    streamingMessage,
    setStreamingMessage,
    executeWorkflowAction,
    getWorkflowActionButtons,
    handleTriggerRebase,
  }
}
