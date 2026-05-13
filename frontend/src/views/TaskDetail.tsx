import { useState, useEffect, useCallback, useRef, memo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import { TaskStatus } from '../lib/api'
import type { Task, Codebase, TaskGitStatus, GitHubPRStatusResponse, PRFeedbackResponse, PRDetailResponse, CustomFieldDefinition } from '../lib/api'
import { useTask, useUpdateTask, useDeleteTask, useEditableField, useCodebases, useProject, useDocument, useUpdateDocument, useImplementationPlan } from '../hooks'
import { useViewTitle } from '../hooks/useViewTitle'
import { useEventHandlerRegistryForStream } from '../hooks/useConversationEventHandlers'
import { useDataStore } from '../stores/dataStore'
import { useUIStore } from '../stores/uiStore'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { ErrorMessage, Card } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'
import AgentChat, { type AgentChatHandle } from '../components/chat/AgentChat'
import GitBranchStatusModal from '../components/modals/GitBranchStatusModal'
import { apiClient } from '../lib/api'
import { useNotificationStore } from '../stores/notificationStore'
import { reportMutationError } from '../lib/errors'
import { useTaskGitStatus } from './hooks/useTaskGitStatus'
import { useTaskEventHandlers } from './hooks/useTaskEventHandlers'
import { useCodeReviewStatus } from './hooks/useCodeReviewStatus'
import { TaskDetailHeader } from '../components/task/TaskDetailHeader'
import { SpecificationTab } from '../components/task/SpecificationTab'
import { PlanTab } from '../components/task/PlanTab'
import { ChangesTab } from '../components/task/ChangesTab'
import { PullRequestTab } from '../components/task/PullRequestTab'
import { SummaryTab } from '../components/task/SummaryTab'
import ChatDetailLayout from '../components/layout/ChatDetailLayout'
import AgentActionBar from '../components/layout/AgentActionBar'
import { TaskArtifactStepper } from '../components/task/TaskArtifactStepper'

const WORKFLOW_ACTION_LABELS: Record<string, string> = {
  'task.create_implementation_plan': 'Create Implementation Plan',
  'task.begin_implementation': 'Begin Implementation',
  'task.rebase_branch': 'Rebase Branch',
  'task.approve_and_merge': 'Approve & Merge',
  'task.approve_and_create_pr': 'Approve & Create PR',
  'task.merge_and_finalise': 'Merge PR & Complete',
  'task.finalise': 'Complete Task',
}

function getActionLabel(
  actionKey: string,
  gitStatus: TaskGitStatus | null,
  prStatus: GitHubPRStatusResponse | null
): string {
  if (actionKey === 'task.merge_and_finalise' && prStatus?.merged) {
    return 'Complete task'
  }

  const needsRebase = (gitStatus?.has_conflicts || gitStatus?.has_uncommitted_base_overlap) && gitStatus.commits_behind > 0
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
  const { data: task, loading, error, refetch } = useTask(id)

  // Fetch documents separately - only when task is loaded with valid document IDs
  const { data: specificationDoc, refetch: refetchSpecification, setData: setSpecificationDoc } = useDocument(task?.specification_document_id ?? null)
  const { data: implementationPlanDoc, refetch: refetchImplementationPlan } = useDocument(task?.implementation_plan_document_id ?? null)
  const { data: implementationPlan, refetch: refetchImplementationPlan2, setData: setImplementationPlan } = useImplementationPlan(task?.implementation_plan_id ? task.id : null)
  const { data: changeSummaryDoc } = useDocument(task?.change_summary_document_id ?? null)

  // Document update mutation
  const { mutate: updateDocument } = useUpdateDocument()

  const { setTask, deleteTask: deleteTaskFromStore } = useDataStore()
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

  const [activeTab, setActiveTab] = useState<'specification' | 'plan' | 'changes' | 'pullrequest' | 'summary'>('specification')

  // PR status for tasks with a PR (pr_open or complete)
  const [prStatus, setPrStatus] = useState<GitHubPRStatusResponse | null>(null)
  const [prStatusLoading, setPrStatusLoading] = useState(false)
  // PR feedback (reviews and comments) for tasks in PR_OPEN or COMPLETE state
  const [prFeedback, setPrFeedback] = useState<PRFeedbackResponse | null>(null)
  // PR detail (CI checks) — fetched lazily when PR tab is first opened
  const [prDetail, setPrDetail] = useState<PRDetailResponse | null>(null)
  const [prDetailLoading, setPrDetailLoading] = useState(false)
  const prDetailFetchedRef = useRef(false)

  // Fetch PR status and feedback when task has a PR (pr_open or complete)
  useEffect(() => {
    setPrDetail(null)
    prDetailFetchedRef.current = false

    if (task?.id && task.github_pr_number && (task.status === TaskStatus.PR_OPEN || task.status === TaskStatus.COMPLETE)) {
      setPrStatusLoading(true)
      apiClient.getTaskPRStatus(task.id)
        .then(setPrStatus)
        .catch(() => setPrStatus(null))
        .finally(() => setPrStatusLoading(false))
      apiClient.getTaskPRFeedback(task.id)
        .then(setPrFeedback)
        .catch(() => setPrFeedback(null))
    } else {
      setPrStatus(null)
      setPrFeedback(null)
    }
  }, [task?.id, task?.status, task?.github_pr_number])

  const handleRefreshPrStatus = useCallback(() => {
    if (!task?.id) return
    setPrStatusLoading(true)
    apiClient.getTaskPRStatus(task.id, true)
      .then(setPrStatus)
      .catch(() => setPrStatus(null))
      .finally(() => setPrStatusLoading(false))
    if (task.codebase_id && task.github_pr_number) {
      setPrDetailLoading(true)
      prDetailFetchedRef.current = true
      apiClient.getPRDetail(task.codebase_id, task.github_pr_number)
        .then(setPrDetail)
        .catch(() => setPrDetail(null))
        .finally(() => setPrDetailLoading(false))
    }
  }, [task?.id, task?.codebase_id, task?.github_pr_number])

  // Lazy-fetch PR detail (CI checks) when PR tab is first opened
  useEffect(() => {
    if (activeTab !== 'pullrequest' || prDetailFetchedRef.current) return
    if (!task?.codebase_id || !task?.github_pr_number) return
    prDetailFetchedRef.current = true
    setPrDetailLoading(true)
    apiClient.getPRDetail(task.codebase_id, task.github_pr_number)
      .then(setPrDetail)
      .catch(() => setPrDetail(null))
      .finally(() => setPrDetailLoading(false))
  }, [activeTab, task?.codebase_id, task?.github_pr_number])


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
    } catch (err) {
      reportMutationError(addNotification, err, {
        entityType: 'task',
        entityId: task.id.toString(),
        entityTitle: task.title,
        fallbackMessage: `Failed to update custom field "${fieldName}"`,
      })
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

  // Use useEditableField hooks to eliminate boilerplate
  const titleField = useEditableField(task?.title || '', saveTitleField)
  const specificationField = useEditableField(specificationDoc?.content || '', saveSpecificationField)

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
      reportMutationError(addNotification, error, {
        entityType: 'task',
        entityId: task?.id.toString() ?? null,
        entityTitle: task?.title ?? null,
        fallbackMessage: 'Failed to delete task',
      })
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

  const markStepRunning = useCallback((stepNumber: number, conversationId: number) => {
    setImplementationPlan(prev => {
      if (!prev) return prev
      return {
        ...prev,
        status: 'executing',
        steps: prev.steps.map(s =>
          s.step_number === stepNumber
            ? { ...s, status: 'running' as const, started_at: new Date().toISOString(), conversation_id: conversationId }
            : s
        ),
      }
    })
  }, [setImplementationPlan])

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

  // Layout state
  const isNarrowRef = useRef(false)
  const handleNarrowChange = useCallback((narrow: boolean) => { isNarrowRef.current = narrow }, [])
  const expandedPanel = useUIStore(s => s.expandedPanel)
  const setExpandedPanel = useUIStore(s => s.setExpandedPanel)

  // Panel attention indicators for narrow mode
  const [chatNeedsAttention, setChatNeedsAttention] = useState(false)
  const [detailsNeedsAttention, setDetailsNeedsAttention] = useState(false)
  const prevStreamingRef = useRef(isConversationStreaming)

  useEffect(() => {
    if (prevStreamingRef.current && !isConversationStreaming && isNarrowRef.current && expandedPanel === 'details') {
      setChatNeedsAttention(true)
    }
    prevStreamingRef.current = isConversationStreaming
  }, [isConversationStreaming, expandedPanel])

  useEffect(() => {
    if (expandedPanel === 'chat') {
      setChatNeedsAttention(false)
    }
  }, [expandedPanel])

  // Details content change detection
  const prevDetailsDataRef = useRef<string>('')

  useEffect(() => {
    const dataFingerprint = JSON.stringify({
      spec: specificationDoc?.content,
      planDoc: implementationPlanDoc?.content,
      planStatus: implementationPlan?.status,
      planSteps: implementationPlan?.steps?.map(s => `${s.step_number}:${s.status}`),
      diff: diffData,
    })
    if (prevDetailsDataRef.current && dataFingerprint !== prevDetailsDataRef.current) {
      if (isNarrowRef.current && expandedPanel === 'chat') {
        setDetailsNeedsAttention(true)
      }
    }
    prevDetailsDataRef.current = dataFingerprint
  }, [specificationDoc?.content, implementationPlanDoc?.content, implementationPlan?.status, implementationPlan?.steps, diffData, expandedPanel])

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
        await refreshGitStatus()
        setStreamingMessage('')
      }
    } catch (error) {
      console.error('Failed to execute workflow action:', error)
      setStreamingMessage('')
      addNotification({
        type: 'system_error',
        priority: 'high',
        entityType: 'task',
        entityId: task.id.toString(),
        entityTitle: task.title ?? null,
        conversationId: null,
        message: error instanceof Error ? error.message : 'Failed to execute workflow action',
        actions: [],
      })
      await refetch()
    }
  }

  // Panel switching callbacks
  const handleSendMessage = useCallback(() => {
    // Auto-switch to chat panel when user sends a message (narrow mode only handled by ChatDetailLayout)
    setExpandedPanel('chat')
  }, [setExpandedPanel])

  const handleWorkflowAction = (actionKey: string) => {
    const config = getButtonConfigForAction(actionKey)
    executeWorkflowAction(actionKey, config.loadingMessage)
    if (isNarrowRef.current && expandedPanel !== 'chat') {
      setExpandedPanel('chat')
    }
  }

  const handleStepClick = useCallback((stepId: string) => {
    // Map stepper step IDs to tab names (stepper uses: specification, plan, changes, pullrequest)
    const stepToTab: Record<string, typeof activeTab> = {
      'specification': 'specification',
      'plan': 'plan',
      'changes': 'changes',
      'pullrequest': 'pullrequest'
    }
    const tab = stepToTab[stepId]
    if (tab) {
      setActiveTab(tab)
      // Auto-switch to details panel on narrow screens
      if (isNarrowRef.current && expandedPanel !== 'details') {
        setExpandedPanel('details')
      }
    }
  }, [setActiveTab, expandedPanel, setExpandedPanel])

  // Helper function for workflow action button configuration
  const getButtonConfigForAction = (actionKey: string) => {
    const configs: Record<string, { loadingMessage: string; className?: string; isDisabled?: () => boolean; title?: () => string | undefined }> = {
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
        isDisabled: () => gitStatus?.base_has_conflicting_uncommitted === true,
        title: () => gitStatus?.base_has_conflicting_uncommitted
          ? 'Main repo has uncommitted changes conflicting with task branch files — commit or stash them first'
          : undefined,
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

  const handleTriggerRebase = useCallback(() => {
    executeWorkflowAction('task.rebase_branch', 'Rebasing branch...')
  }, [task?.id, task?.conversation_id])


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
    <div className="h-full flex flex-col overflow-hidden">
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
        onCodebaseSelect={handleCodebaseSelect}
        onOpenBranchStatusModal={handleOpenBranchStatusModal}
        onDeleteTask={handleDeleteTask}
        deleteLoading={deleteLoading}
        deleteError={deleteError}
        customFields={task.custom_fields}
        customFieldDefinitions={customFieldDefinitions}
        onCustomFieldChange={handleCustomFieldChange}
        customFieldsSaving={updateTaskLoading}
      />

      {/* Main Content Layout */}
      <ChatDetailLayout
        expandedPanel={expandedPanel}
        onNarrowChange={handleNarrowChange}
        onExpandPanel={(panel) => setExpandedPanel(panel)}
        hideDetails={!specificationDoc?.content}
        chatStripProps={{
          isStreaming: isConversationStreaming,
          needsAttention: chatNeedsAttention,
        }}
        detailsStripProps={{
          needsAttention: detailsNeedsAttention,
        }}
        chatContent={
          <AgentChat
            ref={agentChatRef}
            conversationId={task.conversation_id}
            emptyStateMessage="Welcome to the Task Agent!"
            className="h-full flex flex-col overflow-hidden"
            padding="xs"
            isRunningAction={isConversationStreaming}
            actionMessage={streamingMessage}
            workingDir={gitStatus?.worktree_slot_path ?? selectedCodebase?.local_path}
            onConversationReset={handleConversationReset}
          />
        }
        detailsContent={
          <Card padding="none" className="h-full flex flex-col overflow-hidden">
            <TaskArtifactStepper
              activeStep={activeTab}
              onStepClick={handleStepClick}
              taskStatus={task.status}
              hasSpecification={!!specificationDoc?.content}
              hasPlan={!!(task.implementation_plan_id || task.implementation_plan_document_id)}
              planStatus={implementationPlan?.status as 'pending' | 'executing' | 'complete' | 'failed' | undefined}
              hasChanges={!!(task.codebase_id && [TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN, TaskStatus.COMPLETE].includes(task.status))}
              changeCount={diffData?.files?.length}
              hasPR={!!(task.github_pr_number && [TaskStatus.PR_OPEN, TaskStatus.COMPLETE].includes(task.status))}
              prStatus={prStatus ? {
                mergeable_state: prStatus.mergeable_state,
                ci_status: prStatus.ci_status,
                merged: prStatus.merged,
                review_decision: prStatus.review_decision,
              } : undefined}
              hasSummary={!!task.change_summary_document_id}
            />

            <div className="flex-1 min-h-0 p-6 overflow-y-auto">
              {activeTab === 'specification' && (
                <SpecificationTab
                  specificationDoc={specificationDoc}
                  specificationField={specificationField}
                />
              )}

              {activeTab === 'plan' && (
                <PlanTab
                  taskId={task.id}
                  taskStatus={task.status}
                  implementationPlan={implementationPlan}
                  onPlanUpdated={refetchImplementationPlan2}
                  implementationPlanDoc={implementationPlanDoc}
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

              {activeTab === 'pullrequest' && (
                <PullRequestTab
                  prStatus={prStatus}
                  prStatusLoading={prStatusLoading}
                  prFeedback={prFeedback}
                  prDetail={prDetail}
                  prDetailLoading={prDetailLoading}
                  taskStatus={task.status}
                  onRefreshPrStatus={handleRefreshPrStatus}
                  onResolveConflicts={handleResolveConflicts}
                  onSubmitComments={handleSubmitReviewComments}
                  isConversationStreaming={isConversationStreaming}
                />
              )}

              {activeTab === 'summary' && (
                <SummaryTab changeSummaryDoc={changeSummaryDoc} />
              )}
            </div>
          </Card>
        }
        actionBar={
          <AgentActionBar
            conversationId={task.conversation_id}
            onSendMessage={(text) => {
              agentChatRef.current?.sendMessage(text)
              handleSendMessage()
            }}
            isStreaming={isConversationStreaming}
            onStopStream={() => agentChatRef.current?.stopStream()}
            isDisabled={task.status === TaskStatus.COMPLETE || (agentChatRef.current?.sessionExpired ?? false)}
            disabledMessage={
              task.status === TaskStatus.COMPLETE
                ? "Task is complete - chat disabled"
                : "Session expired - please refresh"
            }
            workflowActions={
              task?.available_workflow_actions?.length ? (
                <div className="flex gap-2">
                  {task.available_workflow_actions
                    .filter(action => action.key !== 'task.rebase_branch')
                    .map(action => {
                      const config = getButtonConfigForAction(action.key)
                      const isDisabled = isConversationStreaming || (config.isDisabled?.() ?? false)

                      return (
                        <button
                          key={action.key}
                          onClick={() => handleWorkflowAction(action.key)}
                          disabled={isDisabled}
                          title={config.title?.()}
                          className={`px-3 py-1.5 text-sm font-medium rounded-md border transition-colors ${
                            config.className || 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                          } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                          {getActionLabel(action.key, gitStatus, prStatus)}
                        </button>
                      )
                    })}
                </div>
              ) : undefined
            }
          />
        }
      />

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
