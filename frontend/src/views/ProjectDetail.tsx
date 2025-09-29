import { useState, useEffect, useCallback } from 'react'
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, PlusIcon, XMarkIcon, PencilIcon, CheckIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline'
import ReactMarkdown from 'react-markdown'
import AgentChat from '../components/AgentChat'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import { textColors, layouts, loadingSpinner } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { Project, Task } from '../lib/api'

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [project, setProject] = useState<Project | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  
  // Get tab from URL query params, default to 'home'
  const getTabFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search)
    const tab = params.get('tab') as 'home' | 'board' | 'settings'
    return ['home', 'board', 'settings'].includes(tab) ? tab : 'home'
  }, [location.search])
  
  const [activeTab, setActiveTab] = useState<'board' | 'editor' | 'settings'>(getTabFromUrl() === 'home' ? 'editor' : getTabFromUrl())
  const [showCreateTaskModal, setShowCreateTaskModal] = useState(false)
  const [newTask, setNewTask] = useState({
    title: '',
    status: 'defining',
    codebase_id: null,
    remote_task_id: null
  })
  const [isEditingSpecification, setIsEditingSpecification] = useState(false)
  const [editedSpecification, setEditedSpecification] = useState('')
  const [agentModel, setAgentModel] = useState<string | null>(null)
  const [modelLoading, setModelLoading] = useState(true)

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
      setEditedSpecification(data.specification?.content || '')
    } catch (error) {
      console.error('Failed to fetch project:', error)
    }
  }, [id])

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

  // Update editedSpecification when project loads or editing mode changes
  useEffect(() => {
    if (project && isEditingSpecification) {
      setEditedSpecification(project.specification?.content || '')
    }
  }, [project, isEditingSpecification])

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
        ...newTask,
        project_id: parseInt(id!)
      }
      await apiClient.createTask(id!, taskData)
      await fetchTasks()
      setShowCreateTaskModal(false)
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

  const handleSaveSpecification = async () => {
    try {
      await apiClient.updateProject(id!, { specification: editedSpecification })
      setProject(prev => prev ? { 
        ...prev, 
        specification: { 
          ...prev.specification, 
          content: editedSpecification 
        } 
      } : null)
      setIsEditingSpecification(false)
    } catch (error) {
      console.error('Failed to update project specification:', error)
    }
  }

  const handleCancelEdit = () => {
    setEditedSpecification(project?.specification?.content || '')
    setIsEditingSpecification(false)
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
            <Button onClick={() => setShowCreateTaskModal(true)} size="sm">
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
                    {task.description && (
                      <p className="text-gray-600 dark:text-gray-400 text-xs mb-2 line-clamp-2">
                        {task.description}
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
                {!isEditingSpecification ? (
                  <button
                    onClick={() => {
                      setEditedSpecification(project?.specification?.content || '')
                      setIsEditingSpecification(true)
                    }}
                    className="inline-flex items-center px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <PencilIcon className="w-4 h-4 mr-2" />
                    Edit
                  </button>
                ) : (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={handleSaveSpecification}
                      className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                      <CheckIcon className="w-4 h-4 mr-2" />
                      Save
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      className="inline-flex items-center px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
              
              <div className="flex-1 overflow-hidden flex flex-col">
                {isEditingSpecification ? (
                  <textarea
                    value={editedSpecification}
                    onChange={(e) => setEditedSpecification(e.target.value)}
                    className="w-full flex-1 font-mono text-sm resize-none bg-gray-50 dark:bg-gray-900 px-3 py-2 text-gray-900 dark:text-white border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Enter project specification in Markdown format..."
                  />
                ) : (
                  <div className="h-full overflow-y-auto prose prose-sm dark:prose-invert max-w-none text-left">
                    {project.specification?.content ? (
                      <ReactMarkdown>{project.specification.content}</ReactMarkdown>
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
      {showCreateTaskModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                Create New Task
              </h3>
              <button
                onClick={() => setShowCreateTaskModal(false)}
                className="text-gray-400 hover:text-gray-500 dark:text-gray-500 dark:hover:text-gray-400"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            
            <form onSubmit={handleCreateTask}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Task Title
                </label>
                <input
                  type="text"
                  required
                  value={newTask.title}
                  onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                  placeholder="Enter task title"
                />
              </div>
              

              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Status
                </label>
                <select
                  value={newTask.status}
                  onChange={(e) => setNewTask({ ...newTask, status: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white"
                >
                  <option value="defining" className="text-gray-900 dark:text-white">Defining</option>
                  <option value="planning" className="text-gray-900 dark:text-white">Planning</option>
                  <option value="implementing" className="text-gray-900 dark:text-white">Implementing</option>
                  <option value="reviewing" className="text-gray-900 dark:text-white">Reviewing</option>
                  <option value="complete" className="text-gray-900 dark:text-white">Complete</option>
                </select>
              </div>
              
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowCreateTaskModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Create Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}