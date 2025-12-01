import { useState, useEffect, useCallback, useMemo, memo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, PlusIcon, PencilIcon, CheckIcon, ChatBubbleLeftIcon, XMarkIcon, CodeBracketIcon } from '@heroicons/react/24/outline'
import AgentChat from '../components/chat/AgentChat'
import CreateTaskModal from '../components/modals/CreateTaskModal'
import CreateCodebaseModal from '../components/modals/CreateCodebaseModal'
import { Button, Card, Textarea, Markdown } from '../components/ui'
import { textColors, layouts, loadingSpinner } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { Task, Codebase } from '../lib/api'
import { useModal, useEditableField, useProject, useProjectTasks, useProjectCodebases, useLinkCodebaseToProject, useUnlinkCodebaseFromProject } from '../hooks'
import { useCodebases } from '../hooks/useCodebases'
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
  const { data: project, loading: projectLoading, refetch: refetchProject, setData: setProject } = useProject(id!)
  const { data: tasks, loading: tasksLoading } = useProjectTasks(id!)

  // Project codebases hooks
  const { data: projectCodebases, loading: codebasesLoading, refetch: refetchProjectCodebases } = useProjectCodebases(id!)
  const { data: allCodebases } = useCodebases()
  const { mutate: linkCodebase, loading: linkingCodebase } = useLinkCodebaseToProject()
  const { mutate: unlinkCodebase, loading: unlinkingCodebase } = useUnlinkCodebaseFromProject()

  // State for codebase linking UI
  const [selectedCodebaseToLink, setSelectedCodebaseToLink] = useState<string>('')
  const createCodebaseModal = useModal()

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
    async (value) => {
      const updatedProject = await apiClient.updateProject(id!, {
        specification: value
      })
      // Update the local project data with the response from the API
      setProject(updatedProject)
    }
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
    const groups = tasks.reduce((groups, task) => {
      const status = task.status
      if (!groups[status]) {
        groups[status] = []
      }
      groups[status].push(task)
      return groups
    }, {} as Record<string, Task[]>)

    // Sort tasks within each group by created_at descending (newest first)
    Object.keys(groups).forEach(status => {
      groups[status].sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )
    })

    return groups
  }, [tasks])

  // Compute unlinked codebases for dropdown
  const unlinkedCodebases = useMemo(() => {
    if (!allCodebases || !projectCodebases) return []
    const linkedIds = new Set(projectCodebases.map(c => c.id))
    return allCodebases.filter(c => !linkedIds.has(c.id))
  }, [allCodebases, projectCodebases])

  // Handle linking a codebase to the project
  const handleLinkCodebase = useCallback(async () => {
    if (!selectedCodebaseToLink) return
    try {
      await linkCodebase({ projectId: id!, codebaseId: selectedCodebaseToLink })
      await refetchProjectCodebases()
      setSelectedCodebaseToLink('')
    } catch (error) {
      console.error('Failed to link codebase:', error)
    }
  }, [selectedCodebaseToLink, id, linkCodebase, refetchProjectCodebases])

  // Handle unlinking a codebase from the project
  const handleUnlinkCodebase = useCallback(async (codebaseId: number) => {
    try {
      await unlinkCodebase({ projectId: id!, codebaseId })
      await refetchProjectCodebases()
    } catch (error) {
      console.error('Failed to unlink codebase:', error)
    }
  }, [id, unlinkCodebase, refetchProjectCodebases])

  // Handle new codebase created - link it to the project
  const handleCodebaseCreated = useCallback(async (codebase: Codebase) => {
    try {
      await linkCodebase({ projectId: id!, codebaseId: codebase.id })
      await refetchProjectCodebases()
    } catch (error) {
      console.error('Failed to link newly created codebase:', error)
    }
  }, [id, linkCodebase, refetchProjectCodebases])

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
                    className="w-full font-mono text-sm"
                    fillHeight={true}
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
        <div className="space-y-6">
          {/* Linked Codebases Section */}
          <Card padding="xs">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <CodeBracketIcon className="w-5 h-5 text-green-600 dark:text-green-400" />
                <h3 className={`text-lg font-medium ${textColors.primary}`}>Linked Codebases</h3>
              </div>
            </div>

            {/* Add Codebase Section */}
            <div className="mb-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <div className="flex items-center gap-3">
                <select
                  value={selectedCodebaseToLink}
                  onChange={(e) => setSelectedCodebaseToLink(e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  disabled={linkingCodebase}
                >
                  <option value="">Select a codebase to link...</option>
                  {unlinkedCodebases.map((codebase) => (
                    <option key={codebase.id} value={codebase.id}>
                      {codebase.name}
                    </option>
                  ))}
                </select>
                <Button
                  onClick={handleLinkCodebase}
                  disabled={!selectedCodebaseToLink || linkingCodebase}
                  size="sm"
                  loading={linkingCodebase}
                >
                  <PlusIcon className="w-4 h-4 mr-1" />
                  Link
                </Button>
                <Button
                  onClick={createCodebaseModal.open}
                  variant="secondary"
                  size="sm"
                >
                  <PlusIcon className="w-4 h-4 mr-1" />
                  Create New
                </Button>
              </div>
            </div>

            {/* Linked Codebases List */}
            {codebasesLoading ? (
              <div className="flex justify-center py-4">
                <div className={loadingSpinner}></div>
              </div>
            ) : !projectCodebases || projectCodebases.length === 0 ? (
              <div className="text-center py-8">
                <CodeBracketIcon className="mx-auto h-12 w-12 text-gray-400 mb-3" />
                <p className={`${textColors.secondary} mb-2`}>No codebases linked to this project</p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Link codebases to enable task creation with specific codebases.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {projectCodebases.map((codebase) => (
                  <div
                    key={codebase.id}
                    className="flex items-center justify-between p-3 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg"
                  >
                    <div className="flex-1 min-w-0">
                      <Link
                        to={`/codebases/${codebase.id}`}
                        className="font-medium text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400"
                      >
                        {codebase.name}
                      </Link>
                      <p className="text-sm text-gray-500 dark:text-gray-400 truncate font-mono">
                        {codebase.local_path}
                      </p>
                    </div>
                    <button
                      onClick={() => handleUnlinkCodebase(codebase.id)}
                      className="ml-3 p-1 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                      title="Unlink codebase"
                      disabled={unlinkingCodebase}
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Create Task Modal */}
      <CreateTaskModal
        isOpen={createTaskModal.isOpen}
        onClose={createTaskModal.close}
        projectId={id!}
      />

      {/* Create Codebase Modal */}
      <CreateCodebaseModal
        isOpen={createCodebaseModal.isOpen}
        onClose={createCodebaseModal.close}
        onSuccess={handleCodebaseCreated}
      />

    </div>
  )
}

// Memoize to prevent unnecessary re-renders when other tabs switch
// Only re-render if the project ID actually changes
export default memo(ProjectDetail, (prevProps, nextProps) => {
  return prevProps.id === nextProps.id
})