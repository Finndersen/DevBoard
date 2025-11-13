import { useState, useEffect, useCallback, useRef, memo } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeftIcon, DocumentTextIcon, ClipboardDocumentListIcon, PencilIcon, CheckIcon, XMarkIcon, ChevronDownIcon, CodeBracketIcon } from '@heroicons/react/24/outline'
import type { Task, Codebase, TaskDiffResponse } from '../lib/api'
import { useTask, useUpdateTask, useEditableField, useCodebases, useProject, useTransitionTaskState } from '../hooks'
import { useTabTitle } from '../hooks/useTabTitle'
import { useToolResultHandler } from '../hooks/useConversationEventHandlers'
import { useDataStore } from '../stores/dataStore'
import { Button, Card, Input, StatusBadge, Textarea, ErrorMessage, Markdown } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'
import AgentChat from '../components/chat/AgentChat'
import type { ConversationChatHandle } from '../components/chat/ConversationChat'
import { useApprovals } from '../contexts/ApprovalsContext'
import AllFilesDiffViewer from '../components/documents/AllFilesDiffViewer'
import { apiClient } from '../lib/api'

interface TaskDetailProps {
  id: string
}

function TaskDetail({ id }: TaskDetailProps) {
  const { data: task, loading, error, refetch } = useTask(id)
  const { setTask } = useDataStore()
  const { data: codebases } = useCodebases()

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
  const [isTransitioning, setIsTransitioning] = useState(false)
  const [transitionMessage, setTransitionMessage] = useState<string>('')
  const { registerRefreshHandler, unregisterRefreshHandlers } = useApprovals()

  // State for diff data
  const [diffData, setDiffData] = useState<TaskDiffResponse | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [lastDiffUpdate, setLastDiffUpdate] = useState<string | null>(null)
  
  // Use ref to store refetch function to avoid dependency issues
  const refetchRef = useRef(refetch)
  refetchRef.current = refetch

  // Ref for AgentChat to access its methods
  const agentChatRef = useRef<ConversationChatHandle>(null)

  // Memoize the updateCache function to prevent infinite re-creation
  const updateCache = useCallback(() => {
    // Update local task state with returned data - no refetch needed!
    refetchRef.current()
  }, [])

  // Use enhanced useMutation with optimistic updates (eliminates refetch!)
  const { mutate: updateTask, error: updateError } = useUpdateTask({
    updateCache
  })

  // State transition mutation hook
  const { mutate: transitionState } = useTransitionTaskState({
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

  // Handle codebase selection
  const handleCodebaseSelect = useCallback((codebaseId: number | null) => {
    setShowCodebaseSelector(false)
    updateTask({ id: id!, task: { codebase_id: codebaseId } as unknown as Task })
  }, [updateTask, id])

  // Fetch task diff
  const fetchTaskDiff = useCallback(async () => {
    if (!task?.id) return

    setDiffLoading(true)

    try {
      const response = await apiClient.getTaskDiff(task.id)
      setDiffData(response)
      setLastDiffUpdate(new Date().toISOString())
    } catch (error) {
      console.error('Failed to fetch task diff:', error)
    } finally {
      setDiffLoading(false)
    }
  }, [task?.id])

  // Auto-fetch diff when Changes tab is first opened
  useEffect(() => {
    if (activeTab === 'changes' && !diffData && !diffLoading && task?.codebase_id) {
      fetchTaskDiff()
    }
  }, [activeTab, diffData, diffLoading, task?.codebase_id, fetchTaskDiff])

  // Get selected codebase object
  const selectedCodebase = task && task.codebase_id && codebases
    ? codebases.find((c: Codebase) => c.id === task.codebase_id)
    : null

  // Memoize the refresh handler to prevent infinite loops
  const refreshHandler = useCallback(async () => {
    console.log('TaskDetail: Executing task refresh handler')
    await refetchRef.current() // Refresh task data to get updated specification and implementation plan
  }, [])

  // Register refresh handlers for task document updates
  useEffect(() => {
    if (task?.conversation_id) {
      const conversationId = task.conversation_id

      console.log('TaskDetail: Registering refresh handlers for conversation:', conversationId)

      // Register refresh handler for task-related approvals
      registerRefreshHandler(conversationId, 'refresh_task', refreshHandler)

      // Cleanup on unmount or conversation change
      return () => {
        console.log('TaskDetail: Unregistering refresh handlers for conversation:', conversationId)
        unregisterRefreshHandlers(conversationId)
      }
    }
  }, [task?.conversation_id, registerRefreshHandler, unregisterRefreshHandlers, refreshHandler])

  // Handle specification document updates from MCP tools
  useToolResultHandler(
    (toolName, result) =>
      (toolName.includes('edit_specification') || toolName.includes('set_specification_content')) && !result.is_error,
    async () => {
      console.log('TaskDetail: Specification updated, refetching task data...')
      await refetch()
      // Switch to specification tab to show the updated content
      setActiveTab('specification')
    }
  )

  // Handle implementation plan document updates from MCP tools
  useToolResultHandler(
    (toolName, result) =>
      (toolName.includes('edit_implementation_plan') || toolName.includes('set_implementation_plan_content')) && !result.is_error,
    async () => {
      console.log('TaskDetail: Implementation plan updated, refetching task data...')
      await refetch()
      // Switch to plan tab to show the updated content
      setActiveTab('plan')
    }
  )

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

  // Helper to map task status to prompt action key
  const getPromptActionForState = (state: string): string | null => {
    const mapping: Record<string, string> = {
      'planning': 'task.create_implementation_plan',
      'implementing': 'task.begin_implementation',
    }
    return mapping[state.toLowerCase()] || null
  }

  const handleStateTransition = async (newState: string) => {
    // Set appropriate message based on the new state
    const messages: Record<string, string> = {
      'planning': 'Generating Implementation Plan...',
      'implementing': 'Executing Implementation Plan...',
    }
    const message = messages[newState.toLowerCase()] || 'Processing...'

    setIsTransitioning(true)
    setTransitionMessage(message)
    try {
      // Step 1: Transition state (creates new conversation)
      // No refetch needed - updateCache handles state update
      await transitionState({ id: id!, newState })

      // Step 2: Get appropriate prompt action key for new state
      const actionKey = getPromptActionForState(newState)

      // Step 3: Execute prompt action via ConversationChat
      // This will stream events and display them in real-time
      if (actionKey) {
        await agentChatRef.current?.executePromptAction(actionKey)
      }
    } catch (error) {
      console.error('Failed to transition task state:', error)
    } finally {
      setIsTransitioning(false)
      setTransitionMessage('')
    }
  }


  const getNextStateButton = () => {
    if (!task) return null
    const status = task.status.toLowerCase()

    switch (status) {
      case 'defining':
        return (
          <Button
            onClick={() => handleStateTransition('planning')}
            variant="primary"
          >
            Begin Planning
          </Button>
        )
      case 'planning':
        return (
          <Button
            onClick={() => handleStateTransition('implementing')}
            variant="primary"
            className="bg-green-600 hover:bg-green-700 focus:ring-green-500"
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

  if (loading) {
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
      
      {/* Compact Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-4">
          <Link
            to={project ? `/projects/${project.id}` : '/projects'}
            className={`inline-flex items-center text-sm ${textColors.secondary} hover:text-gray-700 dark:hover:text-gray-300`}
          >
            <ArrowLeftIcon className="w-4 h-4 mr-1" />
            {project ? project.name : 'Projects'}
          </Link>
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
                  className="flex items-center space-x-1 px-2 py-1 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  title="View codebase details"
                >
                  <span className={`font-medium ${textColors.secondary}`}>Codebase:</span>
                  <span className="text-blue-600 dark:text-blue-400 hover:underline">{selectedCodebase.name}</span>
                </Link>
              ) : (
                // Dropdown selector (only shown if no codebase assigned)
                <>
                  <button
                    onClick={() => setShowCodebaseSelector(!showCodebaseSelector)}
                    className={`flex items-center space-x-1 px-2 py-1 rounded text-sm ${textColors.secondary} hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors`}
                    title="Select codebase"
                  >
                    <span className="font-medium">Codebase:</span>
                    <span>None</span>
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

            <span className={`${textColors.secondary} text-sm`}>
              Created {new Date(task.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          
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
                  diffResponse={diffData}
                  loading={diffLoading}
                  onRefresh={fetchTaskDiff}
                  lastUpdated={lastDiffUpdate}
                />
              </div>
            )}
          </div>
        </Card>

        {/* Right Column: Task Agent Chat */}
        <div className="h-full overflow-hidden">
          <AgentChat
            ref={agentChatRef}
            conversationId={task.conversation_id}
            placeholder="Ask me to help with task specification or implementation planning..."
            emptyStateMessage="Welcome to the Task Agent!"
            className="h-full flex flex-col overflow-hidden"
            padding="xs"
            isTransitioning={isTransitioning}
            transitionMessage={transitionMessage}
            onStreamingStarted={() => {
              setIsTransitioning(false)
              setTransitionMessage('')
            }}
          />
        </div>
      </div>

    </div>
  )
}

// Memoize to prevent unnecessary re-renders when other tabs switch
// Only re-render if the task ID actually changes
export default memo(TaskDetail, (prevProps, nextProps) => {
  return prevProps.id === nextProps.id
})