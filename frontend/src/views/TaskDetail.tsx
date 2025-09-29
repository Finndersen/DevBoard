import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeftIcon, DocumentTextIcon, ClipboardDocumentListIcon, PencilIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import ReactMarkdown from 'react-markdown'
import { apiClient } from '../lib/api'
import type { Project, Task } from '../lib/api'
import { useTask, useUpdateTask } from '../hooks'
import { Button, Card, Input, StatusBadge, Textarea, ErrorMessage } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'
import AgentChat from '../components/AgentChat'

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const { data: task, loading, error, refetch } = useTask(id!)
  const { mutate: updateTask, loading: updating, error: updateError } = useUpdateTask()
  const [project, setProject] = useState<Project | null>(null)
  const [activeTab, setActiveTab] = useState<'specification' | 'plan'>('specification')
  const [isEditingSpec, setIsEditingSpec] = useState(false)
  const [isEditingPlan, setIsEditingPlan] = useState(false)
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editedDescription, setEditedDescription] = useState('')
  const [editedPlan, setEditedPlan] = useState('')
  const [editedTitle, setEditedTitle] = useState('')

  useEffect(() => {
    if (task) {
      setEditedDescription(task.specification.content || '')
      setEditedPlan(task.implementation_plan.content || '')
      setEditedTitle(task.title || '')
      // Fetch project details
      fetchProject(task.project_id)
    }
  }, [task])


  const fetchProject = async (projectId: number) => {
    try {
      const data = await apiClient.getProject(projectId)
      setProject(data)
    } catch (error) {
      console.error('Failed to fetch project:', error)
    }
  }

  const handleSaveSpecification = async () => {
    try {
      // Update the specification content - the API should handle converting string to DocumentResponse
      await updateTask({ id: id!, task: { specification: editedDescription } as unknown as Task })
      await refetch()
      setIsEditingSpec(false)
    } catch (error) {
      console.error('Failed to update task specification:', error)
    }
  }

  const handleSavePlan = async () => {
    try {
      // Update the implementation plan content - the API should handle converting string to DocumentResponse
      await updateTask({ id: id!, task: { implementation_plan: editedPlan } as unknown as Task })
      await refetch()
      setIsEditingPlan(false)
    } catch (error) {
      console.error('Failed to update implementation plan:', error)
    }
  }

  const handleCancelSpecEdit = () => {
    setEditedDescription(task?.specification.content || '')
    setIsEditingSpec(false)
  }

  const handleCancelPlanEdit = () => {
    setEditedPlan(task?.implementation_plan.content || '')
    setIsEditingPlan(false)
  }

  const handleSaveTitle = async () => {
    try {
      await updateTask({ id: id!, task: { title: editedTitle } })
      await refetch()
      setIsEditingTitle(false)
    } catch (error) {
      console.error('Failed to update task title:', error)
    }
  }

  const handleCancelTitleEdit = () => {
    setEditedTitle(task?.title || '')
    setIsEditingTitle(false)
  }

  const handleStateTransition = async (newState: string) => {
    try {
      // TODO: Call the state transition API
      // await apiClient.transitionTaskState(id!, newState)
      
      // For now, just update the task status locally
      await updateTask({ id: id!, task: { status: newState } })
      await refetch()
    } catch (error) {
      console.error('Failed to transition task state:', error)
    }
  }


  const getNextStateButton = () => {
    if (!task) return null
    const status = task.status.toLowerCase()
    
    switch (status) {
      case 'pending':
        return (
          <Button
            onClick={() => handleStateTransition('Designing')}
            variant="primary"
          >
            Start Design
          </Button>
        )
      case 'designing':
        return (
          <Button
            onClick={() => handleStateTransition('Planning')}
            variant="primary"
          >
            Begin Planning
          </Button>
        )
      case 'planning':
        return (
          <Button
            onClick={() => handleStateTransition('Implementing')}
            variant="primary"
            className="bg-green-600 hover:bg-green-700 focus:ring-green-500"
          >
            Start Implementation
          </Button>
        )
      case 'implementing':
        return null
      default:
        return null
    }
  }

  const getStatusVariant = (status: string): 'default' | 'success' | 'warning' | 'error' | 'info' => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'warning'
      case 'designing':
      case 'planning':
      case 'implementing':
        return 'info'
      case 'in review':
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
            <StatusBadge variant={getStatusVariant(task.status)}>
              {task.status}
            </StatusBadge>
            <span className={`${textColors.secondary} text-sm`}>
              Created {new Date(task.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          {/* Title Edit Controls */}
          {isEditingTitle ? (
            <div className="flex items-center space-x-2">
              <Input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                className="text-sm h-8"
                style={{ width: `${Math.max(20, editedTitle.length * 0.8 + 5)}ch` }}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveTitle()
                  if (e.key === 'Escape') handleCancelTitleEdit()
                }}
              />
              <Button
                onClick={handleSaveTitle}
                variant="ghost"
                size="sm"
                className="p-1 text-green-600 hover:text-green-700 h-6 w-6"
                title="Save (Enter)"
              >
                <CheckIcon className="w-4 h-4" />
              </Button>
              <Button
                onClick={handleCancelTitleEdit}
                variant="ghost"
                size="sm"
                className={`p-1 ${textColors.secondary} hover:text-gray-700 h-6 w-6`}
                title="Cancel (Escape)"
              >
                <XMarkIcon className="w-4 h-4" />
              </Button>
            </div>
          ) : (
            <Button
              onClick={() => setIsEditingTitle(true)}
              variant="ghost"
              size="sm"
              className="p-1 h-6 w-6"
              title="Edit title"
            >
              <PencilIcon className="w-4 h-4" />
            </Button>
          )}
          
          {/* State Transition Controls */}
          {getNextStateButton()}
        </div>
      </div>

      {/* Main Content Layout */}
      <div className="grid grid-cols-2 gap-6">
        {/* Left Column: Document Content with Tabs */}
        <div>
          {/* Navigation Tabs */}
          <div className="border-b border-gray-200 dark:border-gray-700 mb-4">
            <nav className="-mb-px flex space-x-8">
              {[
                { id: 'specification' as const, name: 'Task Specification', icon: DocumentTextIcon },
                { id: 'plan' as const, name: 'Implementation Plan', icon: ClipboardDocumentListIcon },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  <span>{tab.name}</span>
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          {activeTab === 'specification' && (
            <Card padding="xs">
              <div className={`${layouts.flexBetween} mb-2`}>
                <h3 className={`text-lg font-medium ${textColors.primary}`}>Task Specification</h3>
                {!isEditingSpec ? (
                  <Button
                    onClick={() => setIsEditingSpec(true)}
                    variant="secondary"
                    size="sm"
                    icon={<PencilIcon className="w-4 h-4" />}
                  >
                    Edit
                  </Button>
                ) : (
                  <div className="flex items-center space-x-2">
                    <Button
                      onClick={handleSaveSpecification}
                      variant="primary"
                      size="sm"
                      loading={updating}
                      icon={<CheckIcon className="w-4 h-4" />}
                    >
                      Save
                    </Button>
                    <Button
                      onClick={handleCancelSpecEdit}
                      variant="secondary"
                      size="sm"
                    >
                      Cancel
                    </Button>
                  </div>
                )}
              </div>
              
              {isEditingSpec ? (
                <Textarea
                  value={editedDescription}
                  onChange={(e) => setEditedDescription(e.target.value)}
                  className="w-full h-96 font-mono text-sm"
                  placeholder="Enter task specification in Markdown format..."
                />
              ) : (
                <div className="prose prose-sm dark:prose-invert max-w-none text-left">
                  {task.specification.content ? (
                    <ReactMarkdown>{task.specification.content}</ReactMarkdown>
                  ) : (
                    <p className={`${textColors.secondary} italic`}>No task specification provided. Click Edit to add specification.</p>
                  )}
                </div>
              )}
            </Card>
          )}

          {activeTab === 'plan' && (
            <Card padding="xs">
              <div className={`${layouts.flexBetween} mb-2`}>
                <h3 className={`text-lg font-medium ${textColors.primary}`}>Implementation Plan</h3>
                {!isEditingPlan ? (
                  <Button
                    onClick={() => setIsEditingPlan(true)}
                    variant="secondary"
                    size="sm"
                    icon={<PencilIcon className="w-4 h-4" />}
                  >
                    Edit
                  </Button>
                ) : (
                  <div className="flex items-center space-x-2">
                    <Button
                      onClick={handleSavePlan}
                      variant="primary"
                      size="sm"
                      loading={updating}
                      icon={<CheckIcon className="w-4 h-4" />}
                    >
                      Save
                    </Button>
                    <Button
                      onClick={handleCancelPlanEdit}
                      variant="secondary"
                      size="sm"
                    >
                      Cancel
                    </Button>
                  </div>
                )}
              </div>
              
              {isEditingPlan ? (
                <Textarea
                  value={editedPlan}
                  onChange={(e) => setEditedPlan(e.target.value)}
                  className="w-full h-96 font-mono text-sm"
                  placeholder="Enter implementation plan in Markdown format..."
                />
              ) : (
                <div className="prose prose-sm dark:prose-invert max-w-none text-left">
                  {task.implementation_plan.content ? (
                    <ReactMarkdown>{task.implementation_plan.content}</ReactMarkdown>
                  ) : (
                    <p className={`${textColors.secondary} italic`}>No implementation plan provided. Click Edit to add plan.</p>
                  )}
                </div>
              )}
            </Card>
          )}
        </div>

        {/* Right Column: Task Agent Chat */}
        <div>
          <AgentChat
            title="Task Agent"
            conversationId={task.default_conversation_id}
            placeholder="Ask me to help with task specification or implementation planning..."
            emptyStateMessage="Welcome to the Task Agent!"
            rightHeaderContent={
              <div className={`text-sm ${textColors.secondary}`}>
                Status: {task.status}
              </div>
            }
            className="h-[600px] flex flex-col overflow-hidden"
            padding="xs"
          />
        </div>
      </div>

    </div>
  )
}