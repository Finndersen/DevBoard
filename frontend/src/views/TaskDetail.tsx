import { useState, useEffect, useCallback, useRef, memo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, DocumentTextIcon, ClipboardDocumentListIcon, CodeBracketIcon, ChatBubbleLeftIcon, CheckCircleIcon, ArrowPathIcon, XCircleIcon } from '@heroicons/react/24/outline'
import { TaskStatus } from '../lib/api'
import type { Task, Codebase, TaskGitStatus, GitHubPRStatusResponse, PRFeedbackResponse, CustomFieldDefinition } from '../lib/api'
import { useTask, useUpdateTask, useDeleteTask, useEditableField, useCodebases, useProject, useDocument, useUpdateDocument, useImplementationPlan } from '../hooks'
import { useViewTitle } from '../hooks/useViewTitle'
import { useEventHandlerRegistryForStream } from '../hooks/useConversationEventHandlers'
import { useDataStore } from '../stores/dataStore'
import { useUIStore } from '../stores/uiStore'
import { useIsNarrowContainer } from '../hooks/useMediaQuery'
import CollapsedPanelStrip from '../components/ui/CollapsedPanelStrip'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { Button, Card, ErrorMessage } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'
import AgentChat, { type AgentChatHandle } from '../components/chat/AgentChat'
import GitBranchStatusModal from '../components/modals/GitBranchStatusModal'
import { apiClient } from '../lib/api'
import { useNotificationStore } from '../stores/notificationStore'
import { useTaskGitStatus } from './hooks/useTaskGitStatus'
import { useTaskEventHandlers } from './hooks/useTaskEventHandlers'
import { useCodeReviewStatus } from './hooks/useCodeReviewStatus'
import { TaskDetailHeader } from '../components/task/TaskDetailHeader'
import { SpecificationTab } from '../components/task/SpecificationTab'
import { PlanTab } from '../components/task/PlanTab'
import { ChangesTab } from '../components/task/ChangesTab'
import { CommentsTab } from '../components/task/CommentsTab'
import { SummaryTab } from '../components/task/SummaryTab'
import { CustomFieldsPopover } from '../components/common/CustomFieldsPanel'

const WORKFLOW_ACTION_LABELS: Record<string, string> = {
  'task.create_implementation_plan': 'Create Implementation Plan',
  'task.begin_implementation': 'Begin Implementation',
  'task.rebase_branch': 'Rebase Branch',
  'task.approve_and_merge': 'Approve & Merge',
  'task.approve_and_create_pr': 'Approve & Create PR',
  'task.merge_and_finalise': 'Merge PR & Complete',
  'task.finalise': 'Complete Task',
}

function countPRComments(fb: PRFeedbackResponse): number {
  let count = 0
  for (const r of fb.reviews) {
    if (r.body.trim()) count++
    for (const t of r.comment_threads) {
      count += 1 + t.replies.length
    }
  }
  for (const t of fb.standalone_threads) {
    count += 1 + t.replies.length
  }
  return count
}

function getActionLabel(
  actionKey: string,
  gitStatus: TaskGitStatus | null,
  prStatus: GitHubPRStatusResponse | null
): string {
  if (actionKey === 'task.merge_and_finalise' && prStatus?.merged) {
    return 'Complete task'
  }

  const needsRebase = gitStatus?.has_conflicts && gitStatus.commits_behind > 0
  if (needsRebase) {
    if (actionKey === 'task.approve_and_merge') return 'Rebase & merge locally'
    if (actionKey === 'task.approve_and_create_pr') return 'Rebase & create PR'
  }

  return WORKFLOW_ACTION_LABELS[actionKey] ?? actionKey
}

interface TaskDetailProps {
  id: string
}

function TaskDetail({ id }: TaskDetailProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { data: task, loading, error, refetch } = useTask(id)

  // Fetch documents separately - only when task is loaded with valid document IDs
  const { data: specificationDoc, refetch: refetchSpecification, setData: setSpecificationDoc } = useDocument(task?.specification_document_id ?? null)
  const { data: implementationPlanDoc, refetch: refetchImplementationPlan, setData: setImplementationPlanDoc } = useDocument(task?.implementation_plan_document_id ?? null)
  const { data: implementationPlan, refetch: refetchImplementationPlan2, setData: setImplementationPlan } = useImplementationPlan(task?.implementation_plan_id ? task.id : null)
  const { data: changeSummaryDoc } = useDocument(task?.change_summary_document_id ?? null)

  // Document update mutation
  const { mutate: updateDocument } = useUpdateDocument()

  const { setTask, deleteTask: deleteTaskFromStore, fetchProjectTasks } = useDataStore()
  const { cachedViews, findViewByEntity, evictView, switchTab, invalidateConversations, invalidateTasks } = useUIStore()
  const { data: codebases } = useCodebases()
  const { addNotification } = useNotificationStore()

  // Custom fields state
  const [customFieldDefinitions, setCustomFieldDefinitions] = useState<CustomFieldDefinition[]>([])

  useEffect(() => {
    apiClient.getCustomFieldDefinitions('task')
      .then(setCustomFieldDefinitions)
      .catch(err => console.error('Failed to load task custom field definitions:', err))
  }, [])

  // PR status for tasks with a PR (pr_open or complete)
  const [prStatus, setPrStatus] = useState<GitHubPRStatusResponse | null>(null)
  const [prStatusLoading, setPrStatusLoading] = useState(false)
  // PR feedback (reviews and comments) for tasks in PR_OPEN state
  const [prFeedback, setPrFeedback] = useState<PRFeedbackResponse | null>(null)

  // Fetch PR status when task has a PR (pr_open or complete)
  // Fetch PR feedback only for pr_open (active review)
  useEffect(() => {
    if (task?.id && task.github_pr_number && (task.status === TaskStatus.PR_OPEN || task.status === TaskStatus.COMPLETE)) {
      setPrStatusLoading(true)
      apiClient.getTaskPRStatus(task.id)
        .then(setPrStatus)
        .catch(() => setPrStatus(null))
        .finally(() => setPrStatusLoading(false))
      if (task.status === TaskStatus.PR_OPEN) {
        apiClient.getTaskPRFeedback(task.id)
          .then(setPrFeedback)
          .catch(() => setPrFeedback(null))
      } else {
        setPrFeedback(null)
      }
    } else {
      setPrStatus(null)
      setPrFeedback(null)
    }
  }, [task?.id, task?.status, task?.github_pr_number])

  const handleRefreshPrStatus = useCallback(() => {
    if (!task?.id) return
    setPrStatusLoading(true)
    apiClient.getTaskPRStatus(task.id)
      .then(setPrStatus)
      .catch(() => setPrStatus(null))
      .finally(() => setPrStatusLoading(false))
  }, [task?.id])

  // Handle initial message from navigation state (passed when creating task with description)
  const [pendingInitialMessage, setPendingInitialMessage] = useState<string | null>(null)
  const initialMessageProcessedRef = useRef(false)

  // Check for initial message from navigation state on mount
  useEffect(() => {
    // Only process once per navigation and only if we have task data
    // Validate that the message is for THIS specific task (prevents bug where mounted components from other tabs consume the message)
    if (
      !initialMessageProcessedRef.current &&
      location.state?.initialMessage &&
      location.state?.taskId === parseInt(id) &&
      task?.conversation_id
    ) {
      setPendingInitialMessage(location.state.initialMessage)
      initialMessageProcessedRef.current = true
      // Clear the navigation state to prevent re-sending on refresh
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [location.state?.initialMessage, location.state?.taskId, task?.conversation_id, navigate, location.pathname, id])

  // Clear pending initial message when the task ID changes (navigating to different task)
  // Note: We don't reset initialMessageProcessedRef here to prevent mounted components
  // from consuming initial messages meant for other tasks
  useEffect(() => {
    setPendingInitialMessage(null)
  }, [id])

  // Ref to AgentChat for sending review comments
  const agentChatRef = useRef<AgentChatHandle>(null)

  // Get event handler registry for stream processing
  const eventHandlerRegistry = useEventHandlerRegistryForStream()

  // Get stream store methods for workflow actions
  const migrateStream = useConversationStreamStore(state => state.migrateStream)
  const reconnectStream = useConversationStreamStore(state => state.reconnectStream)
  const addEvent = useConversationStreamStore(state => state.addEvent)
  const updateEventHandlerRegistry = useConversationStreamStore(state => state.updateEventHandlerRegistry)
  const isConversationStreaming = useConversationStreamStore(
    state => task?.conversation_id ? state.isConversationStreaming(task.conversation_id) : false
  )

  // Register event handler registry for the conversation
  // This ensures event handlers work for workflow actions and after navigation
  useEffect(() => {
    if (task?.conversation_id) {
      updateEventHandlerRegistry(task.conversation_id, eventHandlerRegistry)
    }
  }, [task?.conversation_id, eventHandlerRegistry, updateEventHandlerRegistry])

  // Auto-migrate stream if conversation_id changes unexpectedly (e.g. from a refetch)
  const prevTaskConversationIdRef = useRef<number | null>(null)
  useEffect(() => {
    const currentId = task?.conversation_id ?? null
    const prevId = prevTaskConversationIdRef.current
    if (prevId !== null && currentId !== null && prevId !== currentId) {
      console.warn('[TaskDetail] conversation_id changed unexpectedly, auto-migrating:', {
        from: prevId, to: currentId
      })
      migrateStream(prevId, currentId)
    }
    prevTaskConversationIdRef.current = currentId
  }, [task?.conversation_id, migrateStream])

  // Fetch task when id changes (supports both initial mount and tab switching with keep-mounted components)
  useEffect(() => {
    refetch()
  }, [id, refetch])

  // Fetch project data using hook (never fetch automatically)
  const projectId = task?.project_id ?? 0
  const { data: project, refetch: refetchProject } = useProject(projectId, {
    immediate: false
  })

  // Populate DataStore with task data and fetch project when loaded
  useEffect(() => {
    if (task) {
      setTask(task)
      // Fetch associated project if valid project_id exists
      if (task.project_id && task.project_id !== 0) {
        refetchProject()
      }
    }
  }, [task, setTask, refetchProject])

  // Update tab title when task data is loaded
  useViewTitle('task', id)

  const [activeTab, setActiveTab] = useState<'specification' | 'plan' | 'changes' | 'comments' | 'summary'>('specification')
  const [streamingMessage, setStreamingMessage] = useState<string>('')

  // Use ref to store refetch function to avoid dependency issues
  const refetchRef = useRef(refetch)
  refetchRef.current = refetch

  // Clear transition message when streaming starts
  useEffect(() => {
    if (isConversationStreaming && streamingMessage) {
      setStreamingMessage('')
    }
  }, [isConversationStreaming, streamingMessage])

  // Memoize the updateCache function to prevent infinite re-creation
  const updateCache = useCallback(() => {
    refetchRef.current()
  }, [])

  // Use enhanced useMutation with optimistic updates (eliminates refetch!)
  const { mutate: updateTask, loading: updateTaskLoading, error: updateError } = useUpdateTask({
    updateCache
  })

  const handleCustomFieldChange = useCallback(async (fieldName: string, value: unknown) => {
    if (!task) return
    try {
      await updateTask({ id: task.id, task: { custom_fields: { [fieldName]: value } } as unknown as Partial<Task> })
    } catch {
      addNotification({ type: 'error', message: `Failed to update custom field "${fieldName}"` })
    }
  }, [task, updateTask, addNotification])

  // Memoize save functions to prevent infinite re-creation of useEditableField hooks
  const saveTitleField = useCallback((value: string) =>
    updateTask({ id: id!, task: { title: value } }), [updateTask, id]
  )

  const saveSpecificationField = useCallback(async (value: string) => {
    if (!task?.specification_document_id) return
    const updatedDoc = await updateDocument({ id: task.specification_document_id, content: value })
    setSpecificationDoc(updatedDoc)
  }, [task?.specification_document_id, updateDocument, setSpecificationDoc])

  const savePlanField = useCallback(async (value: string) => {
    if (!task?.implementation_plan_document_id) return
    const updatedDoc = await updateDocument({ id: task.implementation_plan_document_id, content: value })
    setImplementationPlanDoc(updatedDoc)
  }, [task?.implementation_plan_document_id, updateDocument, setImplementationPlanDoc])

  // Use useEditableField hooks to eliminate boilerplate
  const titleField = useEditableField(task?.title || '', saveTitleField)
  const specificationField = useEditableField(specificationDoc?.content || '', saveSpecificationField)
  const planField = useEditableField(implementationPlanDoc?.content || '', savePlanField)

  // Delete task mutation
  const { mutate: deleteTask, loading: deleteLoading, error: deleteError } = useDeleteTask()

  // Handle task deletion
  const handleDeleteTask = useCallback(async (deleteBranch: boolean) => {
    if (!task) return

    try {
      await deleteTask(task.id, deleteBranch)

      // Update data store cache
      await deleteTaskFromStore(String(task.id))

      // Determine best target view: tasks-list > project > fallback navigate
      const tasksListView = cachedViews.find(v => v.type === 'tasks-list')
      const projectView = findViewByEntity('project', String(task.project_id))
      const targetView = tasksListView ?? projectView

      // Switch to target view first so evictView doesn't clobber activeViewId
      if (targetView) {
        switchTab(targetView.id)
      }

      // Now safe to evict — task view is no longer active
      const taskView = findViewByEntity('task', String(task.id))
      if (taskView) {
        evictView(taskView.id)
      }

      invalidateTasks()
      invalidateConversations()

      // Show success notification
      addNotification({
        type: 'system_error', // Using system_error as closest match for success
        priority: 'normal',
        entityType: 'project',
        entityId: task.project_id.toString(),
        entityTitle: project?.name || null,
        conversationId: null,
        message: `Task "${task.title}" deleted successfully`,
        actions: []
      })

      if (!targetView) {
        navigate(`/projects/${task.project_id}`)
      }
    } catch (error) {
      console.error('Failed to delete task:', error)
      // Error will be shown via deleteError state
    }
  }, [task, project, cachedViews, deleteTask, deleteTaskFromStore, findViewByEntity, switchTab, evictView, invalidateTasks, invalidateConversations, addNotification, navigate])

  // Handle codebase selection
  const handleCodebaseSelect = useCallback((codebaseId: number | null) => {
    updateTask({ id: id!, task: { codebase_id: codebaseId } as unknown as Task })
  }, [updateTask, id])

  // Get selected codebase object
  const selectedCodebase = task && task.codebase_id && codebases
    ? codebases.find((c: Codebase) => c.id === task.codebase_id)
    : null

  const {
    gitStatus,
    showBranchStatusModal,
    setShowBranchStatusModal,
    branchStatusLoading,
    branchInfo,
    branchInfoLoading,
    diffData,
    diffLoading,
    lastDiffUpdate,
    diffRefreshTimeoutRef,
    handleDiffRefresh,
    handleOpenBranchStatusModal,
    refreshGitStatus,
  } = useTaskGitStatus({
    taskId: task?.id,
    codebaseId: task?.codebase_id,
    activeTab,
  })

  const markStepRunning = useCallback((stepNumber: number) => {
    if (!implementationPlan) return
    setImplementationPlan({
      ...implementationPlan,
      status: 'executing',
      steps: implementationPlan.steps.map(s =>
        s.step_number === stepNumber ? { ...s, status: 'running' as const, started_at: new Date().toISOString() } : s
      )
    })
  }, [implementationPlan, setImplementationPlan])

  useTaskEventHandlers({
    task,
    refetch,
    refetchSpecification,
    refetchImplementationPlan,
    refetchStructuredPlan: refetchImplementationPlan2,
    refreshGitStatus,
    handleDiffRefresh,
    setActiveTab,
    diffRefreshTimeoutRef,
    markStepRunning,
  })

  // Handle conversation reset from AgentChat (when user clears chat history)
  const handleConversationReset = useCallback((newConversationId: number) => {
    const oldConversationId = task?.conversation_id
    if (oldConversationId && oldConversationId !== newConversationId) {
      migrateStream(oldConversationId, newConversationId)
      setStreamingMessage('')
    }
    refetch()
  }, [task?.conversation_id, migrateStream, refetch])

  // Handle review comment submission from diff viewer
  // Uses the AgentChat ref to send through the same flow as regular chat input
  const handleSubmitReviewComments = useCallback((message: string) => {
    agentChatRef.current?.sendMessage(message)
  }, [])

  const handleAutoReview = useCallback(() => {
    agentChatRef.current?.sendMessage('Run `review_code_changes tool` to review your code changes')
  }, [])

  const handleResolveConflicts = useCallback(() => {
    agentChatRef.current?.sendMessage('Rebase on base branch, resolve merge conflicts and force-push changes')
  }, [])

  const { status: codeReviewStatus } = useCodeReviewStatus(task?.conversation_id ?? null)

  // Panel toggle state — based on container width, not viewport
  const [isNarrow, containerRef] = useIsNarrowContainer()
  const expandedPanel = useUIStore(s => s.expandedPanel)
  const setExpandedPanel = useUIStore(s => s.setExpandedPanel)

  // Chat activity indicator
  const [chatNeedsAttention, setChatNeedsAttention] = useState(false)
  const prevStreamingRef = useRef(isConversationStreaming)

  useEffect(() => {
    if (prevStreamingRef.current && !isConversationStreaming && isNarrow && expandedPanel === 'details') {
      setChatNeedsAttention(true)
    }
    prevStreamingRef.current = isConversationStreaming
  }, [isConversationStreaming, isNarrow, expandedPanel])

  useEffect(() => {
    if (expandedPanel === 'chat') {
      setChatNeedsAttention(false)
    }
  }, [expandedPanel])

  // Details content change detection
  const [detailsNeedsAttention, setDetailsNeedsAttention] = useState(false)
  const prevDetailsDataRef = useRef<string>('')

  useEffect(() => {
    const dataFingerprint = JSON.stringify({
      spec: specificationDoc?.content,
      planDoc: implementationPlanDoc?.content,
      plan: implementationPlan,
      diff: diffData,
    })
    if (prevDetailsDataRef.current && dataFingerprint !== prevDetailsDataRef.current) {
      if (isNarrow && expandedPanel === 'chat') {
        setDetailsNeedsAttention(true)
      }
    }
    prevDetailsDataRef.current = dataFingerprint
  }, [specificationDoc?.content, implementationPlanDoc?.content, implementationPlan, diffData, isNarrow, expandedPanel])

  useEffect(() => {
    if (expandedPanel === 'details') {
      setDetailsNeedsAttention(false)
    }
  }, [expandedPanel])

  // Cleanup diff refresh timeout on unmount
  useEffect(() => {
    return () => {
      if (diffRefreshTimeoutRef.current) {
        clearTimeout(diffRefreshTimeoutRef.current)
      }
    }
  }, [])

  const executeWorkflowAction = async (actionKey: string, message: string) => {
    if (!task?.id) return

    setStreamingMessage(message)
    try {
      const result = await apiClient.executeWorkflowAction(task.id, { action_key: actionKey })

      // Refetch task details first — conversation_id may have changed (e.g. new agent role).
      await refetch()

      if (result.conversation_id) {
        if (result.prompt) {
          addEvent(result.conversation_id, {
            event_type: 'message',
            role: 'user',
            text_content: result.prompt,
            timestamp: new Date().toISOString(),
          })
        }
        // Explicitly open WebSocket for the conversation. This is necessary when the
        // workflow action reuses the same conversation (e.g. CreateImplementationPlan),
        // because useStreamSubscription's reconnectAttempted guard prevents re-checking.
        // Safe for new-conversation cases too — reconnectStream's isConversationStreaming
        // guard will no-op if a stream is already active.
        reconnectStream(result.conversation_id)
      } else {
        // No agent execution was started (action completed synchronously)
        setStreamingMessage('')
      }
    } catch (error) {
      console.error('Failed to execute workflow action:', error)
      setStreamingMessage('')
      await refetch()
    }
  }

  const handleTriggerRebase = useCallback(() => {
    executeWorkflowAction('task.rebase_branch', 'Rebasing branch...')
  }, [task?.id, task?.conversation_id])

  // Configuration for workflow action buttons
  const getButtonConfigForAction = (actionKey: string) => {
    const configs: Record<string, { loadingMessage: string; className?: string; isDisabled?: () => boolean }> = {
      'task.create_implementation_plan': {
        loadingMessage: 'Generating Implementation Plan...',
        isDisabled: () => !specificationDoc?.content || specificationDoc.content.trim() === '',
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

  const getWorkflowActionButtons = () => {
    if (!task?.available_workflow_actions?.length) return null

    // Filter out rebase action - it's handled separately in the branch status modal
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
              {getActionLabel(action.key, gitStatus, prStatus)}
            </Button>
          )
        })}
      </div>
    )
  }

  // Only show loading spinner on initial load (when task data doesn't exist yet)
  // Don't show during refetches to avoid UI flash
  if (loading && !task) {
    return (
      <div className={`${layouts.flexCenter} h-64`}>
        <div className={loadingSpinner}></div>
      </div>
    )
  }

  if (error) {
    return (
      <ErrorMessage error={error} retry={refetch} className="max-w-lg mx-auto mt-8" />
    )
  }

  if (!task) {
    return (
      <div className="text-center py-12">
        <h3 className={`text-lg font-medium ${textColors.primary}`}>Task not found</h3>
        <Link to="/projects" className={`mt-4 inline-flex items-center ${textColors.accent} hover:text-blue-500`}>
          <ArrowLeftIcon className="w-4 h-4 mr-2" />
          Back to Projects
        </Link>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="h-full flex flex-col overflow-hidden">
      {/* Error Display */}
      {updateError && (
        <ErrorMessage error={updateError} className="mb-6" />
      )}
      {deleteError && (
        <ErrorMessage error={deleteError} className="mb-6" />
      )}

      {/* Compact Header */}
      <TaskDetailHeader
        task={task}
        project={project}
        titleField={titleField}
        codebases={codebases}
        selectedCodebase={selectedCodebase}
        gitStatus={gitStatus}
        branchStatusLoading={branchStatusLoading}
        prStatus={prStatus}
        prStatusLoading={prStatusLoading}
        onRefreshPrStatus={handleRefreshPrStatus}
        workflowActionButtons={getWorkflowActionButtons()}
        onCodebaseSelect={handleCodebaseSelect}
        onOpenBranchStatusModal={handleOpenBranchStatusModal}
        onDeleteTask={handleDeleteTask}
        deleteLoading={deleteLoading}
        deleteError={deleteError}
        onResolveConflicts={handleResolveConflicts}
        isConversationStreaming={isConversationStreaming}
      />

      {/* Main Content Layout */}
      {isNarrow ? (
        <div className="flex gap-2 flex-1 min-h-0 overflow-hidden">
          {/* Chat panel */}
          <div
            className="relative h-full overflow-hidden transition-[flex] duration-200 ease-in-out"
            style={{ flex: expandedPanel === 'chat' ? '1 1 0%' : '0 0 2.5rem' }}
          >
            <div className={`h-full min-w-0 ${expandedPanel !== 'chat' ? 'invisible' : ''}`}>
              <AgentChat
                ref={agentChatRef}
                conversationId={task.conversation_id}
                placeholder="Ask me to help with task specification or implementation planning..."
                emptyStateMessage="Welcome to the Task Agent!"
                className="h-full flex flex-col overflow-hidden"
                padding="xs"
                isRunningAction={isConversationStreaming}
                actionMessage={streamingMessage}
                initialMessage={pendingInitialMessage}
                onInitialMessageSent={() => setPendingInitialMessage(null)}
                codebaseLocalPath={selectedCodebase?.local_path}
                isDisabled={task.status === TaskStatus.COMPLETE}
                onConversationReset={handleConversationReset}
              />
            </div>
            {expandedPanel !== 'chat' && (
              <div className="absolute inset-0">
                <CollapsedPanelStrip
                  variant="chat"
                  icon="💬"
                  label="Chat"
                  isStreaming={isConversationStreaming}
                  needsAttention={chatNeedsAttention}
                  onClick={() => setExpandedPanel('chat')}
                  className="h-full"
                />
              </div>
            )}
          </div>

          {/* Details panel */}
          <div
            className="relative h-full overflow-hidden transition-[flex] duration-200 ease-in-out"
            style={{ flex: expandedPanel === 'details' ? '1 1 0%' : '0 0 2.5rem' }}
          >
            <Card padding="none" className={`h-full flex flex-col overflow-hidden ${expandedPanel !== 'details' ? 'invisible' : ''}`}>
              {/* Card Header with Tabs */}
              <div className="border-b border-gray-200 dark:border-white/[0.08]">
                <div className="px-6 py-3">
                  <div className="flex items-center justify-between">
                    <nav className="flex space-x-6">
                      {[
                        { id: 'specification' as const, name: 'Task Specification', icon: DocumentTextIcon, badge: null as number | null },
                        ...(task.implementation_plan_id || task.implementation_plan_document_id ? [{ id: 'plan' as const, name: 'Implementation Plan', icon: ClipboardDocumentListIcon, badge: null as number | null }] : []),
                        ...(task.codebase_id && [TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN].includes(task.status) ? [{ id: 'changes' as const, name: 'File Changes', icon: CodeBracketIcon, badge: (diffData?.files?.length ?? null) as number | null }] : []),
                        ...(task.codebase_id && [TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN].includes(task.status) && prFeedback && (prFeedback.reviews.length > 0 || prFeedback.standalone_threads.length > 0) ? [{ id: 'comments' as const, name: 'PR Comments', icon: ChatBubbleLeftIcon, badge: countPRComments(prFeedback) as number | null }] : []),
                        ...(task.change_summary_document_id ? [{ id: 'summary' as const, name: 'Change Summary', icon: DocumentTextIcon, badge: null as number | null }] : []),
                      ].map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`py-1 px-1 font-medium text-sm flex items-center space-x-2 transition-colors ${activeTab === tab.id
                              ? 'text-blue-600 dark:text-blue-400'
                              : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                            }`}
                        >
                          <tab.icon className="w-4 h-4" />
                          <span>{tab.name}</span>
                          {tab.badge != null && tab.badge > 0 && (
                            <span className="text-xs bg-gray-100 dark:bg-white/[0.05] rounded-full px-1.5">
                              {tab.badge}
                            </span>
                          )}
                          {tab.id === 'changes' && task?.status === TaskStatus.IMPLEMENTING && codeReviewStatus === 'reviewed' && (
                            <CheckCircleIcon className="w-3.5 h-3.5 text-green-500" />
                          )}
                          {tab.id === 'plan' && implementationPlan?.status === 'executing' && (
                            <ArrowPathIcon className="w-3.5 h-3.5 text-blue-500 animate-spin" />
                          )}
                          {tab.id === 'plan' && implementationPlan?.status === 'complete' && (
                            <CheckCircleIcon className="w-3.5 h-3.5 text-green-500" />
                          )}
                          {tab.id === 'plan' && implementationPlan?.status === 'failed' && (
                            <XCircleIcon className="w-3.5 h-3.5 text-red-500" />
                          )}
                        </button>
                      ))}
                    </nav>

                    <CustomFieldsPopover
                      customFields={task.custom_fields}
                      fieldDefinitions={customFieldDefinitions}
                      onFieldChange={handleCustomFieldChange}
                      saving={updateTaskLoading}
                    />
                  </div>
                </div>
              </div>

              {/* Tab Content */}
              <div className="flex-1 p-6 overflow-hidden">
                {activeTab === 'specification' && (
                  <SpecificationTab
                    specificationDoc={specificationDoc}
                    specificationField={specificationField}
                  />
                )}

                {activeTab === 'plan' && (
                  <PlanTab
                    taskId={task.id}
                    implementationPlan={implementationPlan}
                    onPlanUpdated={refetchImplementationPlan2}
                    implementationPlanDoc={implementationPlanDoc}
                    planField={planField}
                  />
                )}

                {activeTab === 'changes' && (
                  <ChangesTab
                    branchInfo={branchInfo}
                    diffData={diffData}
                    diffLoading={diffLoading}
                    branchInfoLoading={branchInfoLoading}
                    lastDiffUpdate={lastDiffUpdate}
                    onRefresh={handleDiffRefresh}
                    onSubmitComments={handleSubmitReviewComments}
                    isStreaming={isConversationStreaming}
                    {...(task?.status === TaskStatus.IMPLEMENTING && {
                      codeReviewStatus,
                      onAutoReview: handleAutoReview,
                    })}
                  />
                )}

                {activeTab === 'comments' && prFeedback && (
                  <CommentsTab
                    prFeedback={prFeedback}
                    onSubmitComments={handleSubmitReviewComments}
                  />
                )}

                {activeTab === 'summary' && (
                  <SummaryTab changeSummaryDoc={changeSummaryDoc} />
                )}
              </div>
            </Card>
            {expandedPanel !== 'details' && (
              <div className="absolute inset-0">
                <CollapsedPanelStrip
                  variant="details"
                  icon="📄"
                  label="Details"
                  needsAttention={detailsNeedsAttention}
                  onClick={() => setExpandedPanel('details')}
                  className="h-full"
                />
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 flex-1 min-h-0 overflow-hidden">
          {/* Left Column: Task Agent Chat */}
          <div className="h-full overflow-hidden">
            <AgentChat
              ref={agentChatRef}
              conversationId={task.conversation_id}
              placeholder="Ask me to help with task specification or implementation planning..."
              emptyStateMessage="Welcome to the Task Agent!"
              className="h-full flex flex-col overflow-hidden"
              padding="xs"
              isRunningAction={isConversationStreaming}
              actionMessage={streamingMessage}
              initialMessage={pendingInitialMessage}
              onInitialMessageSent={() => setPendingInitialMessage(null)}
              codebaseLocalPath={selectedCodebase?.local_path}
              isDisabled={task.status === TaskStatus.COMPLETE}
              onConversationReset={handleConversationReset}
            />
          </div>

          {/* Right Column: Document Content with Integrated Tabs */}
          <Card padding="none" className="h-full flex flex-col overflow-hidden">
            {/* Card Header with Tabs */}
            <div className="border-b border-gray-200 dark:border-white/[0.08]">
              <div className="px-6 py-3">
                <div className="flex items-center justify-between">
                  <nav className="flex space-x-6">
                    {[
                      { id: 'specification' as const, name: 'Task Specification', icon: DocumentTextIcon, badge: null as number | null },
                      ...(task.implementation_plan_id || task.implementation_plan_document_id ? [{ id: 'plan' as const, name: 'Implementation Plan', icon: ClipboardDocumentListIcon, badge: null as number | null }] : []),
                      ...(task.codebase_id && [TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN].includes(task.status) ? [{ id: 'changes' as const, name: 'File Changes', icon: CodeBracketIcon, badge: (diffData?.files?.length ?? null) as number | null }] : []),
                      ...(task.codebase_id && [TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN].includes(task.status) && prFeedback && (prFeedback.reviews.length > 0 || prFeedback.standalone_threads.length > 0) ? [{ id: 'comments' as const, name: 'PR Comments', icon: ChatBubbleLeftIcon, badge: countPRComments(prFeedback) as number | null }] : []),
                      ...(task.change_summary_document_id ? [{ id: 'summary' as const, name: 'Change Summary', icon: DocumentTextIcon, badge: null as number | null }] : []),
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`py-1 px-1 font-medium text-sm flex items-center space-x-2 transition-colors ${activeTab === tab.id
                            ? 'text-blue-600 dark:text-blue-400'
                            : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                          }`}
                      >
                        <tab.icon className="w-4 h-4" />
                        <span>{tab.name}</span>
                        {tab.badge != null && tab.badge > 0 && (
                          <span className="text-xs bg-gray-100 dark:bg-white/[0.05] rounded-full px-1.5">
                            {tab.badge}
                          </span>
                        )}
                        {tab.id === 'changes' && task?.status === TaskStatus.IMPLEMENTING && codeReviewStatus === 'reviewed' && (
                          <CheckCircleIcon className="w-3.5 h-3.5 text-green-500" />
                        )}
                        {tab.id === 'plan' && implementationPlan?.status === 'executing' && (
                          <ArrowPathIcon className="w-3.5 h-3.5 text-blue-500 animate-spin" />
                        )}
                        {tab.id === 'plan' && implementationPlan?.status === 'complete' && (
                          <CheckCircleIcon className="w-3.5 h-3.5 text-green-500" />
                        )}
                        {tab.id === 'plan' && implementationPlan?.status === 'failed' && (
                          <XCircleIcon className="w-3.5 h-3.5 text-red-500" />
                        )}
                      </button>
                    ))}
                  </nav>

                  <CustomFieldsPopover
                    customFields={task.custom_fields}
                    fieldDefinitions={customFieldDefinitions}
                    onFieldChange={handleCustomFieldChange}
                    saving={updateTaskLoading}
                  />
                </div>
              </div>
            </div>

            {/* Tab Content */}
            <div className="flex-1 p-6 overflow-hidden">
              {activeTab === 'specification' && (
                <SpecificationTab
                  specificationDoc={specificationDoc}
                  specificationField={specificationField}
                />
              )}

              {activeTab === 'plan' && (
                <PlanTab
                  taskId={task.id}
                  implementationPlan={implementationPlan}
                  onPlanUpdated={refetchImplementationPlan2}
                  implementationPlanDoc={implementationPlanDoc}
                  planField={planField}
                />
              )}

              {activeTab === 'changes' && (
                <ChangesTab
                  branchInfo={branchInfo}
                  diffData={diffData}
                  diffLoading={diffLoading}
                  branchInfoLoading={branchInfoLoading}
                  lastDiffUpdate={lastDiffUpdate}
                  onRefresh={handleDiffRefresh}
                  onSubmitComments={handleSubmitReviewComments}
                  isStreaming={isConversationStreaming}
                  {...(task?.status === TaskStatus.IMPLEMENTING && {
                    codeReviewStatus,
                    onAutoReview: handleAutoReview,
                  })}
                />
              )}

              {activeTab === 'comments' && prFeedback && (
                <CommentsTab
                  prFeedback={prFeedback}
                  onSubmitComments={handleSubmitReviewComments}
                />
              )}

              {activeTab === 'summary' && (
                <SummaryTab changeSummaryDoc={changeSummaryDoc} />
              )}
            </div>
          </Card>

        </div>
      )}

      {/* Branch Status Modal */}
      <GitBranchStatusModal
        isOpen={showBranchStatusModal}
        onClose={() => setShowBranchStatusModal(false)}
        taskId={task.id}
        gitStatus={gitStatus}
        onStatusUpdate={refreshGitStatus}
        onTriggerRebase={handleTriggerRebase}
        isStreaming={isConversationStreaming}
      />

    </div>
  )
}

// Memoize to prevent unnecessary re-renders when other tabs switch
// Only re-render if the task ID actually changes
export default memo(TaskDetail, (prevProps, nextProps) => {
  return prevProps.id === nextProps.id
})
