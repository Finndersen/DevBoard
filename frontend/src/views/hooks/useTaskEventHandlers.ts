import { useCallback, useRef } from 'react'
import type { Task } from '../../lib/api'
import { useToolResultHandler, useSystemEventHandler, useStreamCompleteHandler } from '../../hooks/useConversationEventHandlers'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

interface UseTaskEventHandlersParams {
  task: Task | null
  refetch: () => Promise<void>
  refetchSpecification: () => Promise<void>
  refetchImplementationPlan: () => Promise<void>
  refreshGitStatus: () => Promise<void>
  handleDiffRefresh: (view: string) => Promise<void>
  setActiveTab: (tab: 'specification' | 'plan' | 'changes' | 'summary') => void
  setStreamingMessage: (message: string) => void
  diffRefreshTimeoutRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>
}

export function useTaskEventHandlers({
  task,
  refetch,
  refetchSpecification,
  refetchImplementationPlan,
  refreshGitStatus,
  handleDiffRefresh,
  setActiveTab,
  setStreamingMessage,
  diffRefreshTimeoutRef,
}: UseTaskEventHandlersParams) {
  const migrateStream = useConversationStreamStore(state => state.migrateStream)

  const specificationHandler = useCallback(async (toolName: string, _result: unknown) => {
    if (toolName.includes('edit_task_specification') || toolName.includes('set_task_specification_content')) {
      try {
        console.log('[TaskDetail] specificationHandler: refetching spec and task')
        await refetchSpecification()
        await refetch()
        setActiveTab('specification')
        console.log('[TaskDetail] specificationHandler: completed successfully')
      } catch (error) {
        console.error('Failed to refetch specification document:', error)
      }
    }
  }, [refetchSpecification, refetch, setActiveTab])

  useToolResultHandler(specificationHandler)

  const implementationPlanHandler = useCallback(async (toolName: string, _result: unknown) => {
    if (toolName.includes('edit_task_implementation_plan') || toolName.includes('set_task_implementation_plan_content')) {
      try {
        await refetchImplementationPlan()
        setActiveTab('plan')
      } catch (error) {
        console.error('Failed to refetch implementation plan document:', error)
      }
    }
  }, [refetchImplementationPlan, setActiveTab])

  useToolResultHandler(implementationPlanHandler)

  const fileModificationHandler = useCallback((toolName: string, _result: unknown) => {
    const isFileModification = toolName === 'Edit' || toolName === 'Write'
    const isImplementing = task?.status?.toLowerCase() === 'implementing' && task?.codebase_id

    if (isFileModification && isImplementing) {
      if (diffRefreshTimeoutRef.current) {
        clearTimeout(diffRefreshTimeoutRef.current)
      }
      diffRefreshTimeoutRef.current = setTimeout(() => {
        handleDiffRefresh('all')
      }, 1000)
    }
  }, [task?.status, task?.codebase_id, handleDiffRefresh, diffRefreshTimeoutRef])

  useToolResultHandler(fileModificationHandler)

  const taskCompletionHandler = useCallback(async (toolName: string, _result: unknown) => {
    if (toolName.includes('complete_task_with_local_merge')) {
      await refetch()
    }
  }, [refetch])

  useToolResultHandler(taskCompletionHandler)

  const createPRHandler = useCallback(async (toolName: string, _result: unknown) => {
    if (toolName.includes('create_pull_request')) {
      await refetch()
    }
  }, [refetch])

  useToolResultHandler(createPRHandler)

  const mergePRAndCompleteHandler = useCallback(async (toolName: string, _result: unknown) => {
    if (toolName.includes('merge_pr_and_complete_task')) {
      await refetch()
    }
  }, [refetch])

  useToolResultHandler(mergePRAndCompleteHandler)

  const rebaseHandler = useCallback(async (toolName: string, _result: unknown) => {
    if (toolName.includes('rebase_task_branch')) {
      await refreshGitStatus()
    }
  }, [refreshGitStatus])

  useToolResultHandler(rebaseHandler)

  const systemEventHandler = useCallback(async (event: any) => {
    const isRelevantEventType = event.type === 'task_updated' || event.type === 'branch_rebased' || event.type === 'workspace_allocate'
    const isForThisTask = event.data?.task_id === task?.id

    if (isRelevantEventType && isForThisTask) {
      console.log('[TaskDetail] SystemEvent received:', {
        taskId: task?.id,
        eventType: event.type,
        eventData: event.data,
        timestamp: new Date().toISOString()
      })

      try {
        if (event.type === 'task_updated') {
          const oldConversationId = task?.conversation_id
          const newConversationId = event.data?.updated_fields?.conversation_id

          if (oldConversationId && newConversationId && oldConversationId !== newConversationId) {
            console.log('[TaskDetail] Migrating stream:', { from: oldConversationId, to: newConversationId })
            migrateStream(oldConversationId, newConversationId)
            setStreamingMessage('')
          }

          await refetch()
        }

        if (event.type === 'branch_rebased') {
          await refreshGitStatus()
        }

        if (event.type === 'workspace_allocate') {
          await refreshGitStatus()
        }
      } catch (error) {
        console.error('Failed to handle system event:', error)
      }
    }
  }, [task?.id, task?.conversation_id, migrateStream, refetch, refreshGitStatus, setStreamingMessage])

  useSystemEventHandler(systemEventHandler)

  const streamCompleteHandler = useCallback(() => {
    if (task?.status?.toLowerCase() === 'implementing' && task?.codebase_id) {
      if (diffRefreshTimeoutRef.current) {
        clearTimeout(diffRefreshTimeoutRef.current)
        diffRefreshTimeoutRef.current = null
      }
      handleDiffRefresh('all')
    }
  }, [task?.status, task?.codebase_id, handleDiffRefresh, diffRefreshTimeoutRef])

  useStreamCompleteHandler(streamCompleteHandler)
}
