import { useState, useEffect, useCallback, useRef, memo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, DocumentTextIcon, ClipboardDocumentListIcon, PencilIcon, CheckIcon, XMarkIcon, ChevronDownIcon, CodeBracketIcon, TrashIcon } from '@heroicons/react/24/outline'

// Git branch icon (Y-shape: trunk at bottom splitting into branch at top-right)
const GitBranchIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="20" r="2" />
    <circle cx="12" cy="4" r="2" />
    <circle cx="18" cy="6" r="2" />
    <path d="M12 18 L12 6" />
    <path d="M12 18 Q16 14 18 8" />
  </svg>
)
import type { Task, Codebase, TaskDiffResponse, TaskGitStatus, TaskBranchInfo } from '../lib/api'
import { useTask, useUpdateTask, useDeleteTask, useEditableField, useCodebases, useProject } from '../hooks'
import { useTabTitle } from '../hooks/useTabTitle'
import { useToolResultHandler, useSystemEventHandler, useEventHandlerRegistryForStream, useStreamCompleteHandler } from '../hooks/useConversationEventHandlers'
import { useDataStore } from '../stores/dataStore'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { Button, Card, Input, StatusBadge, Textarea, ErrorMessage, Markdown, ConfirmDialog } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'
import AgentChat from '../components/chat/AgentChat'
import AllFilesDiffViewer from '../components/documents/AllFilesDiffViewer'
import GitBranchStatusModal from '../components/modals/GitBranchStatusModal'
import { apiClient } from '../lib/api'
import { useNotificationStore } from '../stores/notificationStore'

interface TaskDetailProps {
  id: string
}

function TaskDetail({ id }: TaskDetailProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { data: task, loading, error, refetch } = useTask(id)
  const { setTask, deleteTask: deleteTaskFromStore, fetchProjectTasks } = useDataStore()
  const { data: codebases } = useCodebases()
  const { addNotification } = useNotificationStore()

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

  // Get event handler registry for passing to stream processor
  const eventHandlerRegistry = useEventHandlerRegistryForStream()

  // Get stream store methods for workflow actions
  const startStream = useConversationStreamStore(state => state.startStream)
  const migrateStream = useConversationStreamStore(state => state.migrateStream)
  const isConversationStreaming = useConversationStreamStore(
    state => task?.conversation_id ? state.isConversationStreaming(task.conversation_id) : false
  )

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
  useTabTitle('task', id)

  const [activeTab, setActiveTab] = useState<'specification' | 'plan' | 'changes'>('specification')
  const [showCodebaseSelector, setShowCodebaseSelector] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState<string>('')
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteBranch, setDeleteBranch] = useState(true)
  const [gitStatus, setGitStatus] = useState<TaskGitStatus | null>(null)
  const [showBranchStatusModal, setShowBranchStatusModal] = useState(false)
  const [branchStatusLoading, setBranchStatusLoading] = useState(false)

  // State for branch info and diff data
  const [branchInfo, setBranchInfo] = useState<TaskBranchInfo | null>(null)
  const [branchInfoLoading, setBranchInfoLoading] = useState(false)
  const [diffData, setDiffData] = useState<TaskDiffResponse | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [lastDiffUpdate, setLastDiffUpdate] = useState<string | null>(null)
  const diffRefreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
    // Update local task state with returned data - no refetch needed!
    refetchRef.current()
  }, [])

  // Use enhanced useMutation with optimistic updates (eliminates refetch!)
  const { mutate: updateTask, error: updateError } = useUpdateTask({
    updateCache
  })

  // Memoize save functions to prevent infinite re-creation of useEditableField hooks
  const saveTitleField = useCallback((value: string) => 
    updateTask({ id: id!, task: { title: value }}), [updateTask, id]
  )
  
  const saveSpecificationField = useCallback((value: string) => 
    updateTask({ id: id!, task: { specification: value } as unknown as Task }), [updateTask, id]
  )
  
  const savePlanField = useCallback((value: string) => 
    updateTask({ id: id!, task: { implementation_plan: value } as unknown as Task }), [updateTask, id]
  )

  // Use useEditableField hooks to eliminate boilerplate
  const titleField = useEditableField(task?.title || '', saveTitleField)
  const specificationField = useEditableField(task?.specification.content || '', saveSpecificationField)
  const planField = useEditableField(task?.implementation_plan?.content || '', savePlanField)

  // Delete task mutation
  const { mutate: deleteTask, loading: deleteLoading, error: deleteError } = useDeleteTask()

  // Handle task deletion
  const handleDeleteTask = useCallback(async () => {
    if (!task) return

    try {
      await deleteTask(task.id, deleteBranch)

      // Update cache
      await deleteTaskFromStore(String(task.id))
      await fetchProjectTasks(String(task.project_id))

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

      // Navigate to parent project
      navigate(`/projects/${task.project_id}`)
    } catch (error) {
      console.error('Failed to delete task:', error)
      // Error will be shown via deleteError state
    } finally {
      setShowDeleteConfirm(false)
    }
  }, [task, project, deleteTask, deleteBranch, deleteTaskFromStore, fetchProjectTasks, addNotification, navigate])

  // Handle codebase selection
  const handleCodebaseSelect = useCallback((codebaseId: number | null) => {
    setShowCodebaseSelector(false)
    updateTask({ id: id!, task: { codebase_id: codebaseId } as unknown as Task })
  }, [updateTask, id])

  // Fetch task branch info (commits list and uncommitted status)
  const fetchTaskBranchInfo = useCallback(async () => {
    if (!task?.id) return

    setBranchInfoLoading(true)

    try {
      const response = await apiClient.getTaskBranchInfo(task.id)
      setBranchInfo(response)
    } catch (error) {
      console.error('Failed to fetch task branch info:', error)
    } finally {
      setBranchInfoLoading(false)
    }
  }, [task?.id])

  // Fetch task diff
  const fetchTaskDiff = useCallback(async (view: string) => {
    if (!task?.id) return

    setDiffLoading(true)

    try {
      const response = await apiClient.getTaskDiff(task.id, view)
      setDiffData(response)
      setLastDiffUpdate(new Date().toISOString())
    } catch (error) {
      console.error('Failed to fetch task diff:', error)
    } finally {
      setDiffLoading(false)
    }
  }, [task?.id])

  // Combined refresh handler that refetches both branch info and diff
  const handleDiffRefresh = useCallback(async (view: string) => {
    if (!task?.id) return

    // First refetch branch info to find new commits
    await fetchTaskBranchInfo()
    // Then refetch the diff for the selected view
    await fetchTaskDiff(view)
  }, [task?.id, fetchTaskBranchInfo, fetchTaskDiff])

  // Auto-fetch branch info and initial diff when Changes tab is first opened
  useEffect(() => {
    if (activeTab === 'changes' && !branchInfo && !branchInfoLoading && task?.codebase_id) {
      // First fetch branch info to populate dropdown
      fetchTaskBranchInfo().then(() => {
        // Then fetch 'all' view as default
        fetchTaskDiff('all')
      })
    }
  }, [activeTab, branchInfo, branchInfoLoading, task?.codebase_id, fetchTaskBranchInfo, fetchTaskDiff])

  // Get selected codebase object
  const selectedCodebase = task && task.codebase_id && codebases
    ? codebases.find((c: Codebase) => c.id === task.codebase_id)
    : null

  // Fetch git status on task load to show branch icon in header
  useEffect(() => {
    if (task?.id && task?.codebase_id) {
      apiClient.getTaskGitStatus(task.id)
        .then(status => setGitStatus(status))
        .catch(error => {
          console.error('Failed to fetch git status:', error)
          setGitStatus(null)
        })
    }
  }, [task?.id, task?.codebase_id])

  // Handle opening branch status modal
  const handleOpenBranchStatusModal = useCallback(async () => {
    if (!task?.id) return

    setBranchStatusLoading(true)
    setShowBranchStatusModal(true)

    try {
      const status = await apiClient.getTaskGitStatus(task.id)
      setGitStatus(status)
    } catch (error) {
      console.error('Failed to fetch git status:', error)
      setGitStatus(null)
    } finally {
      setBranchStatusLoading(false)
    }
  }, [task?.id])

  // Refresh git status (called after modal actions)
  const refreshGitStatus = useCallback(async () => {
    if (!task?.id) return

    try {
      const status = await apiClient.getTaskGitStatus(task.id)
      setGitStatus(status)
    } catch (error) {
      console.error('Failed to refresh git status:', error)
    }
  }, [task?.id])


  // Memoize matchers and handlers to prevent re-registration on every render
  const specificationMatcher = useCallback(
    (toolName: string) => toolName.includes('edit_task_specification') || toolName.includes('set_task_specification_content'),
    []
  )

  const specificationHandler = useCallback(async (result: any) => {
    try {
      await refetch()
      // Switch to specification tab to show the updated content
      setActiveTab('specification')
    } catch (error) {
      console.error('Failed to refetch task after specification update:', error)
    }
  }, [task?.specification?.content?.length, refetch, setActiveTab])

  // Handle specification document updates from MCP tools
  useToolResultHandler(specificationMatcher, specificationHandler)

  const implementationPlanMatcher = useCallback(
    (toolName: string) => toolName.includes('edit_task_implementation_plan') || toolName.includes('set_task_implementation_plan_content'),
    []
  )

  const implementationPlanHandler = useCallback(async (result: any) => {
    try {
      await refetch()
      // Switch to plan tab to show the updated content
      setActiveTab('plan')
    } catch (error) {
      console.error('Failed to refetch task after implementation plan update:', error)
    }
  }, [task?.implementation_plan?.content?.length, refetch, setActiveTab])

  // Handle implementation plan document updates from MCP tools
  useToolResultHandler(implementationPlanMatcher, implementationPlanHandler)

  // Handle file modification tool results to refresh diff view
  const fileModificationMatcher = useCallback(
    (toolName: string) => toolName === 'Edit' || toolName === 'Write',
    []
  )

  const fileModificationHandler = useCallback(() => {
    if (task?.status?.toLowerCase() !== 'implementing' || !task?.codebase_id) {
      return
    }

    if (diffRefreshTimeoutRef.current) {
      clearTimeout(diffRefreshTimeoutRef.current)
    }

    diffRefreshTimeoutRef.current = setTimeout(() => {
      handleDiffRefresh('all')
    }, 500)
  }, [task?.status, task?.codebase_id, handleDiffRefresh])

  useToolResultHandler(fileModificationMatcher, fileModificationHandler)

  const systemEventMatcher = useCallback((event: any) => {
    return event.type === 'task_updated' && event.data?.task_id === task?.id
  }, [task?.id])

  const systemEventHandler = useCallback(async (event: any) => {
    // Check if conversation_id is changing
    const oldConversationId = task?.conversation_id
    const newConversationId = event.data?.updated_fields?.conversation_id

    console.log('[TaskDetail] SystemEvent received:', {
      taskId: task?.id,
      eventType: event.type,
      oldConversationId,
      newConversationId,
      currentTaskConversationId: task?.conversation_id,
      eventData: event.data,
      timestamp: new Date().toISOString()
    })

    try {
      // Migrate stream FIRST (before refetch updates conversation_id in state)
      // This prevents race condition where component re-renders with new conversation_id
      // but stream is still registered under old conversation_id
      if (oldConversationId && newConversationId && oldConversationId !== newConversationId) {
        console.log('[TaskDetail] Migrating stream:', { from: oldConversationId, to: newConversationId })
        migrateStream(oldConversationId, newConversationId)
        // Clear streaming message immediately after migration
        // The isConversationStreaming check in the effect won't work during migration
        // because task.conversation_id hasn't updated yet
        setStreamingMessage('')
      }

      const refetchStartTime = Date.now()
      console.log('[TaskDetail] STARTING refetch:', {
        taskId: task?.id,
        currentConversationId: task?.conversation_id,
        timestamp: new Date().toISOString()
      })
      // THEN refetch task to get updated status and conversation_id
      const updatedTaskResult = await refetch()
      console.log('[TaskDetail] COMPLETED refetch:', {
        durationMs: Date.now() - refetchStartTime,
        oldConversationId: task?.conversation_id,
        newConversationId: updatedTaskResult?.conversation_id,
        conversationIdChanged: task?.conversation_id !== updatedTaskResult?.conversation_id,
        timestamp: new Date().toISOString()
      })
    } catch (error) {
      console.error('Failed to refetch task after update event:', error)
      // Don't throw - allow other handlers and stream to continue
    }
  }, [task?.id, task?.status, task?.conversation_id, migrateStream, refetch])

  // Handle task updates from SystemEvents (emitted during workflow actions)
  useSystemEventHandler(systemEventMatcher, systemEventHandler)

  // Handle stream completion - refresh diff view when agent finishes during implementation phase
  const streamCompleteHandler = useCallback(() => {
    // Only refresh diff when task is in implementing status
    if (task?.status?.toLowerCase() === 'implementing' && task?.codebase_id) {
      // Refresh the 'all' view to show latest changes
      handleDiffRefresh('all')
    }
  }, [task?.status, task?.codebase_id, handleDiffRefresh])

  useStreamCompleteHandler(streamCompleteHandler)

  // Cleanup diff refresh timeout on unmount
  useEffect(() => {
    return () => {
      if (diffRefreshTimeoutRef.current) {
        clearTimeout(diffRefreshTimeoutRef.current)
      }
    }
  }, [])

  // Close codebase selector when clicking outside
  useEffect(() => {
    if (!showCodebaseSelector) return

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      if (!target.closest('.relative')) {
        setShowCodebaseSelector(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showCodebaseSelector])

  const executeWorkflowAction = async (actionKey: string, message: string) => {
    if (!task?.id || !task?.conversation_id) return

    console.log('[TaskDetail] executeWorkflowAction:', {
      actionKey,
      taskId: task.id,
      conversationId: task.conversation_id
    })

    setStreamingMessage(message)
    try {
      // Fetch existing conversation messages to preserve history
      const existingMessages = await apiClient.getConversationMessages(task.conversation_id)
      console.log('[TaskDetail] Fetched existing messages:', existingMessages.length)

      // Create workflow action stream
      const stream = apiClient.streamWorkflowAction(task.id, { action_key: actionKey })

      // Use store startStream for unified streaming behavior
      // Pass existing messages to preserve conversation history
      // This immediately sets isStreaming=true in the store, which disables buttons
      // Event handlers are already registered via hooks at component level
      // Pass eventHandlerRegistry so tool results and system events are processed
      console.log('[TaskDetail] Starting stream with conversation_id:', task.conversation_id)
      await startStream(task.conversation_id, stream, eventHandlerRegistry, existingMessages)
      console.log('[TaskDetail] Stream completed')
    } catch (error) {
      console.error('Failed to execute workflow action:', error)
      // Clear transition message on error
      setStreamingMessage('')
    }
  }


  const getNextStateButton = () => {
    if (!task) return null
    const status = task.status.toLowerCase()

    switch (status) {
      case 'defining':
        return (
          <Button
            onClick={() => executeWorkflowAction('task.create_implementation_plan', 'Generating Implementation Plan...')}
            variant="primary"
            disabled={!task.specification?.content || task.specification.content.trim() === '' || isConversationStreaming}
          >
            Begin Planning
          </Button>
        )
      case 'planning':
        return (
          <Button
            onClick={() => executeWorkflowAction('task.begin_implementation', 'Starting Implementation...')}
            variant="primary"
            className="bg-green-600 hover:bg-green-700 focus:ring-green-500"
            disabled={isConversationStreaming}
          >
            Start Implementation
          </Button>
        )
      case 'implementing':
      case 'reviewing':
      case 'complete':
        return null
      default:
        return null
    }
  }

  const getStatusVariant = (status: string): 'default' | 'success' | 'warning' | 'error' | 'info' => {
    switch (status.toLowerCase()) {
      case 'defining':
      case 'planning':
      case 'implementing':
        return 'info'
      case 'reviewing':
        return 'warning'
      case 'complete':
        return 'success'
      default:
        return 'default'
    }
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
    <div>
      {/* Error Display */}
      {updateError && (
        <ErrorMessage error={updateError} className="mb-6" />
      )}
      {deleteError && (
        <ErrorMessage error={deleteError} className="mb-6" />
      )}
      
      {/* Compact Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-3">
            {/* Task Title Display and Edit */}
            {titleField.isEditing ? (
              <div className="flex items-center space-x-2">
                <Input
                  type="text"
                  value={titleField.editedValue}
                  onChange={(e) => titleField.setEditedValue(e.target.value)}
                  className="text-lg font-bold h-8"
                  style={{ width: `${Math.max(20, titleField.editedValue.length * 0.8 + 5)}ch` }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') titleField.save()
                    if (e.key === 'Escape') titleField.cancelEditing()
                  }}
                />
                <Button
                  onClick={(e) => {
                    e.preventDefault()
                    titleField.save()
                  }}
                  variant="secondary"
                  size="sm"
                  className="p-1.5 min-w-[28px] h-7 border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400 dark:border-green-600 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50"
                  title="Save (Enter)"
                  loading={titleField.saving}
                >
                  <CheckIcon className="w-4 h-4" />
                </Button>
                <Button
                  onClick={(e) => {
                    e.preventDefault()
                    titleField.cancelEditing()
                  }}
                  variant="secondary"
                  size="sm"
                  className="p-1.5 min-w-[28px] h-7 border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
                  title="Cancel (Escape)"
                >
                  <XMarkIcon className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <h1 className={`text-xl font-bold ${textColors.primary}`}>
                  {task.title}
                </h1>
                <Button
                  onClick={(e) => {
                    e.preventDefault()
                    titleField.startEditing()
                  }}
                  variant="ghost"
                  size="sm"
                  className="p-2 text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
                  title="Edit title"
                >
                  <PencilIcon className="w-4 h-4" />
                </Button>
              </div>
            )}
            <StatusBadge variant={getStatusVariant(task.status)}>
              {task.status}
            </StatusBadge>

            {/* Codebase Display/Selector */}
            <div className="relative">
              {selectedCodebase ? (
                // Read-only display with link to codebase detail
                <Link
                  to={`/codebases/${selectedCodebase.id}`}
                  className="flex items-center space-x-1.5 px-2 py-1 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  title="View codebase details"
                >
                  <CodeBracketIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                  <span className="text-blue-600 dark:text-blue-400 hover:underline">{selectedCodebase.name}</span>
                </Link>
              ) : (
                // Dropdown selector (only shown if no codebase assigned)
                <>
                  <button
                    onClick={() => setShowCodebaseSelector(!showCodebaseSelector)}
                    className={`flex items-center space-x-1.5 px-2 py-1 rounded text-sm ${textColors.secondary} hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors`}
                    title="Select codebase"
                  >
                    <CodeBracketIcon className="w-4 h-4" />
                    <span className="italic">No codebase</span>
                    <ChevronDownIcon className="w-3 h-3" />
                  </button>

                  {showCodebaseSelector && (
                    <div className="absolute top-full left-0 mt-1 w-64 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-10">
                      <div className="max-h-64 overflow-y-auto">
                        {codebases && codebases.map((codebase: Codebase) => (
                          <button
                            key={codebase.id}
                            onClick={() => handleCodebaseSelect(codebase.id)}
                            className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 ${
                              codebase.id === task.codebase_id ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : textColors.primary
                            } ${codebase.id !== codebases[0].id ? 'border-t border-gray-100 dark:border-gray-700' : ''}`}
                          >
                            <div className="font-medium">{codebase.name}</div>
                            <div className={`text-xs ${textColors.secondary} truncate`}>{codebase.local_path}</div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Branch Status Icon - only shown when task has a branch_name */}
            {gitStatus?.branch_name && (
              <button
                onClick={handleOpenBranchStatusModal}
                className={`flex items-center space-x-1.5 px-2 py-1 rounded text-sm border transition-colors ${
                  gitStatus.worktree_slot_path
                    ? 'border-blue-400 bg-blue-50 text-blue-600 hover:bg-blue-100 dark:border-blue-500 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50'
                    : 'border-gray-300 hover:bg-gray-100 dark:border-gray-600 dark:hover:bg-gray-800 ' + textColors.secondary
                }`}
                title={gitStatus.branch_name}
                disabled={branchStatusLoading}
              >
                <GitBranchIcon className="w-4 h-4" />
                {gitStatus.commits_behind > 0 && (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                    {gitStatus.commits_behind} behind
                  </span>
                )}
              </button>
            )}
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          {/* Delete Button */}
          <Button
            onClick={() => setShowDeleteConfirm(true)}
            variant="ghost"
            size="sm"
            icon={<TrashIcon className="w-4 h-4" />}
            className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:text-red-500 dark:hover:text-red-400 dark:hover:bg-red-900/20"
            title="Delete task"
            aria-label="Delete task"
          >
            Delete
          </Button>

          {/* State Transition Controls */}
          {getNextStateButton()}
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-200px)] overflow-hidden">
        {/* Left Column: Document Content with Integrated Tabs */}
        <Card padding="none" className="h-full flex flex-col overflow-hidden">
          {/* Card Header with Tabs */}
          <div className="border-b border-gray-200 dark:border-gray-700">
            <div className="px-6 py-3">
              <div className="flex items-center justify-between">
                {/* Navigation Tabs */}
                <nav className="flex space-x-6">
                  {[
                    { id: 'specification' as const, name: 'Task Specification', icon: DocumentTextIcon },
                    ...(task.implementation_plan ? [{ id: 'plan' as const, name: 'Implementation Plan', icon: ClipboardDocumentListIcon }] : []),
                    ...(task.codebase_id && ['implementing', 'reviewing', 'complete'].includes(task.status.toLowerCase()) ? [{ id: 'changes' as const, name: 'File Changes', icon: CodeBracketIcon }] : []),
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`py-1 px-1 font-medium text-sm flex items-center space-x-2 transition-colors ${
                        activeTab === tab.id
                          ? 'text-blue-600 dark:text-blue-400'
                          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                      }`}
                    >
                      <tab.icon className="w-4 h-4" />
                      <span>{tab.name}</span>
                    </button>
                  ))}
                </nav>

                {/* Action Buttons */}
                <div>
                  {activeTab === 'specification' && (
                    !specificationField.isEditing ? (
                      <Button
                        onClick={specificationField.startEditing}
                        variant="secondary"
                        size="sm"
                        icon={<PencilIcon className="w-4 h-4" />}
                      >
                        Edit
                      </Button>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <Button
                          onClick={specificationField.save}
                          variant="primary"
                          size="sm"
                          loading={specificationField.saving}
                          icon={<CheckIcon className="w-4 h-4" />}
                        >
                          Save
                        </Button>
                        <Button
                          onClick={specificationField.cancelEditing}
                          variant="secondary"
                          size="sm"
                        >
                          Cancel
                        </Button>
                      </div>
                    )
                  )}

                  {activeTab === 'plan' && (
                    !planField.isEditing ? (
                      <Button
                        onClick={planField.startEditing}
                        variant="secondary"
                        size="sm"
                        icon={<PencilIcon className="w-4 h-4" />}
                      >
                        Edit
                      </Button>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <Button
                          onClick={planField.save}
                          variant="primary"
                          size="sm"
                          loading={planField.saving}
                          icon={<CheckIcon className="w-4 h-4" />}
                        >
                          Save
                        </Button>
                        <Button
                          onClick={planField.cancelEditing}
                          variant="secondary"
                          size="sm"
                        >
                          Cancel
                        </Button>
                      </div>
                    )
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Tab Content */}
          <div className="flex-1 p-6 overflow-hidden">
            {activeTab === 'specification' && (
              <div className="h-full flex flex-col">
                {specificationField.isEditing ? (
                  <Textarea
                    value={specificationField.editedValue}
                    onChange={(e) => specificationField.setEditedValue(e.target.value)}
                    fillHeight={true}
                    placeholder="Enter task specification in Markdown format..."
                  />
                ) : (
                  <div className="h-full overflow-y-auto">
                    {task.specification.content ? (
                      <Markdown>{task.specification.content}</Markdown>
                    ) : (
                      <p className={`${textColors.secondary} italic`}>No task specification provided. Click Edit to add specification.</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'plan' && (
              <div className="h-full flex flex-col">
                {planField.isEditing ? (
                  <Textarea
                    value={planField.editedValue}
                    onChange={(e) => planField.setEditedValue(e.target.value)}
                    fillHeight={true}
                    placeholder="Enter implementation plan in Markdown format..."
                  />
                ) : (
                  <div className="h-full overflow-y-auto">
                    {task.implementation_plan?.content ? (
                      <Markdown>{task.implementation_plan.content}</Markdown>
                    ) : (
                      <p className={`${textColors.secondary} italic`}>No implementation plan provided. Click Edit to add plan.</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'changes' && (
              <div className="h-full overflow-hidden">
                <AllFilesDiffViewer
                  branchInfo={branchInfo}
                  diffResponse={diffData}
                  loading={diffLoading || branchInfoLoading}
                  onRefresh={handleDiffRefresh}
                  lastUpdated={lastDiffUpdate}
                />
              </div>
            )}
          </div>
        </Card>

        {/* Right Column: Task Agent Chat */}
        <div className="h-full overflow-hidden">
          <AgentChat
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
          />
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDeleteTask}
        title="Delete Task"
        message={
          <div>
            <p>Are you sure you want to delete "{task.title}"? This will permanently delete the task, its specification, implementation plan, conversations, and all associated data. This action cannot be undone.</p>
            {gitStatus?.branch_exists && gitStatus.commits_ahead > 0 && (
              <div style={{ marginTop: '12px', padding: '8px', backgroundColor: '#fff3cd', borderRadius: '4px' }}>
                ⚠️ Branch has {gitStatus.commits_ahead} unmerged commit{gitStatus.commits_ahead !== 1 ? 's' : ''}
              </div>
            )}
            {gitStatus?.branch_exists && (
              <label style={{ display: 'flex', alignItems: 'center', marginTop: '16px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={deleteBranch}
                  onChange={(e) => setDeleteBranch(e.target.checked)}
                  style={{ marginRight: '8px' }}
                />
                <span>
                  Also delete git branch {gitStatus?.branch_name && `"${gitStatus.branch_name}"`}
                </span>
              </label>
            )}
            {!gitStatus?.branch_exists && gitStatus?.branch_name && (
              <div style={{ marginTop: '12px', fontSize: '0.9em', color: '#666', fontStyle: 'italic' }}>
                Branch "{gitStatus.branch_name}" does not exist
              </div>
            )}
          </div>
        }
        confirmText="Delete Task"
        cancelText="Cancel"
        variant="danger"
        loading={deleteLoading}
      />

      {/* Branch Status Modal */}
      <GitBranchStatusModal
        isOpen={showBranchStatusModal}
        onClose={() => setShowBranchStatusModal(false)}
        taskId={task.id}
        gitStatus={gitStatus}
        onStatusUpdate={refreshGitStatus}
      />
    </div>
  )
}

// Memoize to prevent unnecessary re-renders when other tabs switch
// Only re-render if the task ID actually changes
export default memo(TaskDetail, (prevProps, nextProps) => {
  return prevProps.id === nextProps.id
})