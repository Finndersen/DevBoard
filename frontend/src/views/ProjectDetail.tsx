import { useState, useEffect, useCallback } from 'react'
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, PlusIcon, PencilIcon, CheckIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline'
import AgentChat from '../components/chat/AgentChat'
import { Button, Card, Input, Textarea, Modal, Markdown } from '../components/ui'
import { textColors, layouts, loadingSpinner } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { Project, Task } from '../lib/api'
import { useModal, useEditableField } from '../hooks'
import { useTabTitle } from '../hooks/useTabTitle'
import { useDataStore } from '../stores/dataStore'
import { useApprovals } from '../contexts/ApprovalsContext'

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { setProject: setStoreProject } = useDataStore()

  // Update tab title when project data is loaded
  useTabTitle('project', id)
  const [project, setProject] = useState<Project | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  
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
  const [newTask, setNewTask] = useState({
    title: '',
    status: 'defining',
    codebase_id: null,
    remote_task_id: null
  })
  const [agentModel, setAgentModel] = useState<string | null>(null)
  const [modelLoading, setModelLoading] = useState(true)
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

  const fetchProject = useCallback(async () => {
    try {
      const data = await apiClient.getProject(id!)
      setProject(data)
      setStoreProject(data)
    } catch (error) {
      console.error('Failed to fetch project:', error)
    }
  }, [id, setStoreProject])

  const fetchTasks = useCallback(async () => {
    try {
      const data = await apiClient.getProjectTasks(id!)
      setTasks(data)
    } catch (error) {
      console.error('Failed to fetch tasks:', error)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchProject()
    fetchTasks()
    fetchAgentModel()
  }, [fetchProject, fetchTasks])

  // Register refresh handlers for project document updates
  useEffect(() => {
    if (project?.default_conversation_id) {
      const conversationId = project.default_conversation_id
      
      console.log('ProjectDetail: Registering refresh handlers for conversation:', conversationId)
      
      // Register refresh handler for project-related approvals
      registerRefreshHandler(conversationId, 'refresh_project', async () => {
        console.log('ProjectDetail: Executing project refresh handler')
        await fetchProject() // Refresh project data to get updated specification
      })

      // Cleanup on unmount or conversation change
      return () => {
        console.log('ProjectDetail: Unregistering refresh handlers for conversation:', conversationId)
        unregisterRefreshHandlers(conversationId)
      }
    }
  }, [project?.default_conversation_id, fetchProject, registerRefreshHandler, unregisterRefreshHandlers])

  const fetchAgentModel = async () => {
    try {
      const data = await apiClient.getAgentModel('project')
      setAgentModel(data.model_id)
    } catch (error) {
      console.error('Failed to fetch agent model:', error)
    } finally {
      setModelLoading(false)
    }
  }

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const taskData = {
        title: newTask.title,
        status: newTask.status,
        codebase_id: newTask.codebase_id,
        remote_task_id: newTask.remote_task_id,
        default_conversation_id: null,
        specification: {
          id: 0, // Will be set by backend
          document_type: 'task_specification',
          content: '',
          content_hash: '',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        implementation_plan: {
          id: 0, // Will be set by backend
          document_type: 'implementation_plan',
          content: '',
          content_hash: '',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }
      }
      await apiClient.createTask(id!, taskData)
      await fetchTasks()
      createTaskModal.close()
      setNewTask({ 
        title: '', 
        status: 'defining',
        codebase_id: null,
        remote_task_id: null
      })
    } catch (error) {
      console.error('Failed to create task:', error)
    }
  }


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

  const groupTasksByStatus = (tasks: Task[]) => {
    return tasks.reduce((groups, task) => {
      const status = task.status
      if (!groups[status]) {
        groups[status] = []
      }
      groups[status].push(task)
      return groups
    }, {} as Record<string, Task[]>)
  }

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

  const taskGroups = groupTasksByStatus(tasks)
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
            title="Agent"
            conversationId={project.default_conversation_id}
            placeholder="Ask a question about this project..."
            emptyStateMessage="Ask me anything about this project!"
            rightHeaderContent={
              <div className={`text-sm ${textColors.secondary}`}>
                {modelLoading ? (
                  <span>Loading...</span>
                ) : agentModel ? (
                  <span>Model: {agentModel}</span>
                ) : (
                  <span>Model: Unknown</span>
                )}
              </div>
            }
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
      <Modal 
        isOpen={createTaskModal.isOpen}
        onClose={createTaskModal.close}
        title="Create New Task"
        maxWidth="md"
      >
        <form onSubmit={handleCreateTask}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Task Title
              </label>
              <Input
                type="text"
                required
                value={newTask.title}
                onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                placeholder="Enter task title"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Status
              </label>
              <select
                value={newTask.status}
                onChange={(e) => setNewTask({ ...newTask, status: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
              >
                <option value="defining">Defining</option>
                <option value="planning">Planning</option>
                <option value="implementing">Implementing</option>
                <option value="reviewing">Reviewing</option>
                <option value="complete">Complete</option>
              </select>
            </div>
          </div>
          
          <div className="flex justify-end space-x-3 mt-6">
            <Button
              type="button"
              variant="secondary"
              onClick={createTaskModal.close}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
            >
              Create Task
            </Button>
          </div>
        </form>
      </Modal>

    </div>
  )
}