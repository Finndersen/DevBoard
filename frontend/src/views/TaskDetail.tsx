import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeftIcon, ChatBubbleLeftIcon, DocumentTextIcon, ClipboardDocumentListIcon, PencilIcon, CheckIcon } from '@heroicons/react/24/outline'
import ReactMarkdown from 'react-markdown'
import { apiClient } from '../lib/api'
import type { Task, Project } from '../lib/api'
import TaskPlanningChat from '../components/TaskPlanningChat'

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const [task, setTask] = useState<Task | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'specification' | 'plan' | 'conversation'>('specification')
  const [isEditingSpec, setIsEditingSpec] = useState(false)
  const [isEditingPlan, setIsEditingPlan] = useState(false)
  const [editedDescription, setEditedDescription] = useState('')
  const [editedPlan, setEditedPlan] = useState('')

  useEffect(() => {
    fetchTask()
  }, [id])

  const fetchTask = async () => {
    try {
      const data = await apiClient.getTask(id!)
      setTask(data)
      setEditedDescription(data.description || '')
      setEditedPlan(data.implementation_plan || '')
      // Fetch project details
      fetchProject(data.project_id)
    } catch (error) {
      console.error('Failed to fetch task:', error)
    } finally {
      setLoading(false)
    }
  }

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
      await apiClient.updateTask(id!, { description: editedDescription })
      setTask(prev => prev ? { ...prev, description: editedDescription } : null)
      setIsEditingSpec(false)
    } catch (error) {
      console.error('Failed to update task specification:', error)
    }
  }

  const handleSavePlan = async () => {
    try {
      await apiClient.updateTask(id!, { implementation_plan: editedPlan })
      setTask(prev => prev ? { ...prev, implementation_plan: editedPlan } : null)
      setIsEditingPlan(false)
    } catch (error) {
      console.error('Failed to update implementation plan:', error)
    }
  }

  const handleCancelSpecEdit = () => {
    setEditedDescription(task?.description || '')
    setIsEditingSpec(false)
  }

  const handleCancelPlanEdit = () => {
    setEditedPlan(task?.implementation_plan || '')
    setIsEditingPlan(false)
  }

  const handleStateTransition = async (newState: string) => {
    try {
      // TODO: Call the state transition API
      // await apiClient.transitionTaskState(id!, newState)
      
      // For now, just update the task status locally
      setTask(prev => prev ? { ...prev, status: newState } : null)
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
          <button
            onClick={() => handleStateTransition('Designing')}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Start Design
          </button>
        )
      case 'designing':
        return (
          <button
            onClick={() => handleStateTransition('Planning')}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Begin Planning
          </button>
        )
      case 'planning':
        return (
          <button
            onClick={() => handleStateTransition('Implementing')}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
          >
            Start Implementation
          </button>
        )
      case 'implementing':
        return (
          <button
            onClick={() => setActiveTab('conversation')}
            className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 text-sm font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            View Progress
          </button>
        )
      default:
        return null
    }
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400'
      case 'designing':
        return 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/20 dark:text-indigo-400'
      case 'planning':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400'
      case 'implementing':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900/20 dark:text-purple-400'
      case 'in review':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400'
      case 'complete':
        return 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400'
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="text-center py-12">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">Task not found</h3>
        <Link to="/projects" className="mt-4 inline-flex items-center text-blue-600 hover:text-blue-500">
          <ArrowLeftIcon className="w-4 h-4 mr-2" />
          Back to Projects
        </Link>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <Link
            to={project ? `/projects/${project.id}` : '/projects'}
            className="inline-flex items-center text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
          >
            <ArrowLeftIcon className="w-5 h-5 mr-2" />
            {project ? project.name : 'Projects'}
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{task.title}</h1>
            <div className="flex items-center space-x-2 mt-1">
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(task.status)}`}>
                {task.status}
              </span>
              <span className="text-gray-500 dark:text-gray-400 text-sm">
                Created {new Date(task.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
        
        {/* State Transition Controls */}
        <div className="flex items-center space-x-3">
          {getNextStateButton()}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'specification' as const, name: 'Task Specification', icon: DocumentTextIcon },
            { id: 'plan' as const, name: 'Implementation Plan', icon: ClipboardDocumentListIcon },
            { id: 'conversation' as const, name: 'Planning Agent', icon: ChatBubbleLeftIcon },
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
        <div className="max-w-4xl mx-auto">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">Task Specification</h3>
              {!isEditingSpec ? (
                <button
                  onClick={() => setIsEditingSpec(true)}
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
                    onClick={handleCancelSpecEdit}
                    className="inline-flex items-center px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
            
            {isEditingSpec ? (
              <textarea
                value={editedDescription}
                onChange={(e) => setEditedDescription(e.target.value)}
                className="w-full h-96 px-3 py-2 text-gray-900 dark:text-gray-100 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                placeholder="Enter task specification in Markdown format..."
              />
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none text-left">
                {task.description ? (
                  <ReactMarkdown>{task.description}</ReactMarkdown>
                ) : (
                  <p className="text-gray-500 dark:text-gray-400 italic">No task specification provided. Click Edit to add specification.</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'plan' && (
        <div className="max-w-4xl mx-auto">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">Implementation Plan</h3>
              {!isEditingPlan ? (
                <button
                  onClick={() => setIsEditingPlan(true)}
                  className="inline-flex items-center px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <PencilIcon className="w-4 h-4 mr-2" />
                  Edit
                </button>
              ) : (
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleSavePlan}
                    className="inline-flex items-center px-3 py-1 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <CheckIcon className="w-4 h-4 mr-2" />
                    Save
                  </button>
                  <button
                    onClick={handleCancelPlanEdit}
                    className="inline-flex items-center px-3 py-1 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
            
            {isEditingPlan ? (
              <textarea
                value={editedPlan}
                onChange={(e) => setEditedPlan(e.target.value)}
                className="w-full h-96 px-3 py-2 text-gray-900 dark:text-gray-100 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                placeholder="Enter implementation plan in Markdown format..."
              />
            ) : (
              <div className="prose prose-sm dark:prose-invert max-w-none text-left">
                {task.implementation_plan ? (
                  <ReactMarkdown>{task.implementation_plan}</ReactMarkdown>
                ) : (
                  <p className="text-gray-500 dark:text-gray-400 italic">No implementation plan provided. Click Edit to add plan.</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'conversation' && (
        <div className="max-w-4xl mx-auto">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 h-[600px]">
            <div className="flex items-center mb-4">
              <ChatBubbleLeftIcon className="w-5 h-5 mr-2 text-blue-600" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">Planning Agent</h3>
              <div className="ml-auto">
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Status: {task.status}
                </span>
              </div>
            </div>
            <div className="h-full border border-gray-200 dark:border-gray-600 rounded-lg">
              <TaskPlanningChat taskId={parseInt(id!)} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}