import { useState, useEffect, useCallback, useMemo, memo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, PlusIcon, PencilIcon, CheckIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline'
import AgentChat from '../components/chat/AgentChat'
import CreateTaskModal from '../components/modals/CreateTaskModal'
import { Button, Card, Textarea, Markdown } from '../components/ui'
import { textColors, layouts, loadingSpinner } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { Task } from '../lib/api'
import { useModal, useEditableField, useProject, useProjectTasks } from '../hooks'
import { useTabTitle } from '../hooks/useTabTitle'
import { useDataStore } from '../stores/dataStore'
import { useApprovals } from '../contexts/ApprovalsContext'

interface ProjectDetailProps {
  id: string
}

function ProjectDetail({ id }: ProjectDetailProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { setProject: setStoreProject } = useDataStore()

  // Update tab title when project data is loaded
  useTabTitle('project', id)

  // Fetch data using hooks
  const { data: project, loading: projectLoading, refetch: refetchProject } = useProject(id!)
  const { data: tasks, loading: tasksLoading } = useProjectTasks(id!)

  // Combined loading state
  const loading = projectLoading || tasksLoading
  
  // Get tab from URL query params, default to 'home'
  const getTabFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search)
    const tab = params.get('tab') as 'home' | 'board' | 'settings'
    return ['home', 'board', 'settings'].includes(tab) ? tab : 'home'
  }, [location.search])
  
  const [activeTab, setActiveTab] = useState<'board' | 'editor' | 'settings'>(() => {
    const tab = getTabFromUrl()
    return tab === 'home' ? 'editor' : tab as 'board' | 'editor' | 'settings'
  })

  const { registerRefreshHandler, unregisterRefreshHandlers } = useApprovals()

  // Use new custom hooks
  const createTaskModal = useModal()
  const specificationField = useEditableField(
    project?.specification?.content || '',
    (value) => apiClient.updateProject(id!, { 
      specification: {
        ...project!.specification,
        content: value
      }
    })
  )

  // Update URL when tab changes
  const handleTabChange = (tab: 'board' | 'editor' | 'settings') => {
    setActiveTab(tab)
    const urlTab = tab === 'editor' ? 'home' : tab
    const params = new URLSearchParams(location.search)
    params.set('tab', urlTab)
    navigate(`/projects/${id}?${params.toString()}`, { replace: true })
  }

  // Update activeTab when URL changes
  useEffect(() => {
    const urlTab = getTabFromUrl()
    const internalTab = urlTab === 'home' ? 'editor' : urlTab
    setActiveTab(internalTab)
  }, [getTabFromUrl])

  // Store project in DataStore when loaded
  useEffect(() => {
    if (project) {
      setStoreProject(project)
    }
  }, [project, setStoreProject])

  // Register refresh handlers for project document updates
  useEffect(() => {
    if (project?.default_conversation_id) {
      const conversationId = project.default_conversation_id
      
      console.log('ProjectDetail: Registering refresh handlers for conversation:', conversationId)
      
      // Register refresh handler for project-related approvals
      registerRefreshHandler(conversationId, 'refresh_project', async () => {
        console.log('ProjectDetail: Executing project refresh handler')
        await refetchProject() // Refresh project data to get updated specification
      })

      // Cleanup on unmount or conversation change
      return () => {
        console.log('ProjectDetail: Unregistering refresh handlers for conversation:', conversationId)
        unregisterRefreshHandlers(conversationId)
      }
    }
  }, [project?.default_conversation_id, refetchProject, registerRefreshHandler, unregisterRefreshHandlers])

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'defining':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400'
      case 'planning':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
      case 'implementing':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900/20 dark:text-purple-400'
      case 'reviewing':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400'
      case 'complete':
        return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400'
    }
  }

  // Memoize task grouping to avoid recalculation on every render
  const taskGroups = useMemo(() => {
    if (!tasks) return {} as Record<string, Task[]>
    return tasks.reduce((groups, task) => {
      const status = task.status
      if (!groups[status]) {
        groups[status] = []
      }
      groups[status].push(task)
      return groups
    }, {} as Record<string, Task[]>)
  }, [tasks])

  if (loading) {
    return (
      <div className={`${layouts.flexCenter} h-64`}>
        <div className={loadingSpinner}></div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <h3 className={`text-lg font-medium ${textColors.primary}`}>Project not found</h3>
        <Link to="/projects" className="mt-4 inline-flex items-center text-blue-600 hover:text-blue-500">
          <ArrowLeftIcon className="w-4 h-4 mr-2" />
          Back to Projects
        </Link>
      </div>
    )
  }

  const statusColumns = ['defining', 'planning', 'implementing', 'reviewing', 'complete']

  return (
    <div>
      {/* Navigation Tabs with Project Name and Actions */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-4">
        <div className="flex items-center justify-between relative">
          {/* Left: Navigation Tabs */}
          <nav className="-mb-px flex space-x-8">
            {[
              { id: 'editor' as const, name: 'Home', icon: ChatBubbleLeftIcon },
              { id: 'board' as const, name: 'Tasks', icon: null },
              { id: 'settings' as const, name: 'Settings', icon: null },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors flex items-center ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                {tab.icon && <tab.icon className="w-4 h-4 mr-2" />}
                {tab.name}
              </button>
            ))}
          </nav>
          
          {/* Center: Project Name */}
          <div className="absolute left-1/2 transform -translate-x-1/2">
            <h1 className={`text-xl font-bold ${textColors.primary}`}>
              {project?.name}
            </h1>
          </div>
          
          {/* Right: Actions */}
          <div className="flex items-center">
            <Button onClick={createTaskModal.open} size="sm">
              <PlusIcon className="w-4 h-4 mr-2" />
              New Task
            </Button>
          </div>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'board' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
          {statusColumns.map((status) => (
            <Card key={status} padding="xs" className="bg-gray-50 dark:bg-gray-800">
              <h3 className={`font-medium ${textColors.primary} mb-4 flex items-center justify-between`}>
                {status}
                <span className="bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs px-2 py-1 rounded-full">
                  {taskGroups[status]?.length || 0}
                </span>
              </h3>
              
              <div className="space-y-3">
                {taskGroups[status]?.map((task) => (
                  <Link
                    key={task.id}
                    to={`/tasks/${task.id}`}
                    className="block bg-white dark:bg-gray-700 rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow border border-gray-200 dark:border-gray-600"
                  >
                    <h4 className="font-medium text-gray-900 dark:text-white text-sm mb-2">
                      {task.title}
                    </h4>
                    {task.specification?.content && (
                      <p className="text-gray-600 dark:text-gray-400 text-xs mb-2 line-clamp-2">
                        {task.specification.content}
                      </p>
                    )}
                    <div className="flex items-center justify-between">
                      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                        {task.status}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {activeTab === 'editor' && (
        <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6 h-[calc(100vh-200px)] overflow-hidden">
          {/* Left Side - Project Specification */}
          <div className="flex flex-col overflow-hidden">
            {/* Specification Document Section */}
            <Card padding="xs" className="h-full flex flex-col overflow-hidden">
              <div className="flex items-center justify-between mb-2 flex-shrink-0">
                <h3 className={`text-lg font-medium ${textColors.primary}`}>Project Specification</h3>
                {!specificationField.isEditing ? (
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
                )}
              </div>
              
              <div className="flex-1 overflow-hidden flex flex-col">
                {specificationField.isEditing ? (
                  <Textarea
                    value={specificationField.editedValue}
                    onChange={(e) => specificationField.setEditedValue(e.target.value)}
                    className="w-full flex-1 font-mono text-sm resize-none"
                    placeholder="Enter project specification in Markdown format..."
                  />
                ) : (
                  <div className="h-full overflow-y-auto">
                    {project.specification?.content ? (
                      <Markdown>{project.specification.content}</Markdown>
                    ) : (
                      <p className="text-gray-500 dark:text-gray-400 italic">No project specification provided. Click Edit to add specification.</p>
                    )}
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Right Side - Chat */}
          <AgentChat
            conversationId={project.default_conversation_id}
            placeholder="Ask a question about this project..."
            emptyStateMessage="Ask me anything about this project!"
            className="h-full flex flex-col overflow-hidden"
          />
        </div>
      )}

      {activeTab === 'settings' && (
        <Card padding="xs">
          <h3 className={`text-lg font-medium ${textColors.primary} mb-4`}>Project Settings</h3>
          <p className={textColors.secondary}>Project settings configuration will be implemented here.</p>
        </Card>
      )}

      {/* Create Task Modal */}
      <CreateTaskModal
        isOpen={createTaskModal.isOpen}
        onClose={createTaskModal.close}
        projectId={id!}
      />

    </div>
  )
}

// Memoize to prevent unnecessary re-renders when other tabs switch
// Only re-render if the project ID actually changes
export default memo(ProjectDetail, (prevProps, nextProps) => {
  return prevProps.id === nextProps.id
})