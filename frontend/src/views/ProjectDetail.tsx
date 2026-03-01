import { useState, useEffect, useCallback, useMemo, memo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, PlusIcon, PencilIcon, CheckIcon, ChatBubbleLeftIcon, XMarkIcon, CodeBracketIcon } from '@heroicons/react/24/outline'
import AgentChat from '../components/chat/AgentChat'
import CreateTaskModal from '../components/modals/CreateTaskModal'
import CreateCodebaseModal from '../components/modals/CreateCodebaseModal'
import { Button, Card, Textarea, Markdown, Input } from '../components/ui'
import { textColors, layouts, loadingSpinner } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { Task, Codebase } from '../lib/api'
import { useModal, useEditableField, useProject, useProjectTasks, useProjectCodebases, useLinkCodebaseToProject, useUnlinkCodebaseFromProject, useDocument } from '../hooks'
import { useCodebases } from '../hooks/useCodebases'
import { useTabTitle } from '../hooks/useTabTitle'
import { useToolResultHandler } from '../hooks/useConversationEventHandlers'
import { useDataStore } from '../stores/dataStore'
import { useConversationStreamStore } from '../stores/conversationStreamStore'

interface ProjectDetailProps {
  id: string
}

function ProjectDetail({ id }: ProjectDetailProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { setProject: setStoreProject } = useDataStore()
  const migrateStream = useConversationStreamStore(state => state.migrateStream)

  // Update tab title when project data is loaded
  useTabTitle('project', id)

  // Fetch data using hooks
  const { data: project, loading: projectLoading, refetch: refetchProject, setData: setProject } = useProject(id!)

  // Fetch specification document separately - only when project is loaded with valid document ID
  const { data: specificationDoc, refetch: refetchSpecification } = useDocument(project?.specification_document_id ?? null)

  const { data: tasks, loading: tasksLoading } = useProjectTasks(id!)

  // Project codebases hooks
  const { data: projectCodebases, loading: codebasesLoading, refetch: refetchProjectCodebases } = useProjectCodebases(id!)
  const { data: allCodebases, refetch: refetchAllCodebases } = useCodebases()
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

  // Use new custom hooks
  const createTaskModal = useModal()
  const specificationField = useEditableField(
    specificationDoc?.content || '',
    async (value) => {
      await apiClient.updateProject(id!, {
        specification: value
      })
      // Refetch the specification document to get updated content
      await refetchSpecification()
    }
  )

  const saveDescriptionField = useCallback(
    async (value: string) => {
      await apiClient.updateProject(id!, { description: value })
      refetchProject()
    },
    [id, refetchProject]
  )

  const descriptionField = useEditableField(project?.description || '', saveDescriptionField)

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

  // Handle project specification updates from MCP tools during stream processing
  const projectSpecificationMatcher = useCallback(
    (toolName: string) => toolName.includes('edit_project_specification') || toolName.includes('set_project_specification_content'),
    []
  )

  const projectSpecificationHandler = useCallback(async () => {
    await refetchSpecification()
  }, [refetchSpecification])

  useToolResultHandler(projectSpecificationMatcher, projectSpecificationHandler)

  // Handle conversation reset from AgentChat (when user clears chat history)
  const handleConversationReset = useCallback((newConversationId: number) => {
    const oldConversationId = project?.default_conversation_id
    if (oldConversationId && oldConversationId !== newConversationId) {
      migrateStream(oldConversationId, newConversationId)
    }
    refetchProject()
  }, [project?.default_conversation_id, migrateStream, refetchProject])

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
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
      await refetchAllCodebases()
    } catch (error) {
      console.error('Failed to link newly created codebase:', error)
    }
  }, [id, linkCodebase, refetchProjectCodebases, refetchAllCodebases])

  // Only show loading spinner on initial load (when project data doesn't exist yet)
  // Don't show during refetches to avoid UI flash
  if (loading && !project) {
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

  const statusColumns = ['planning', 'implementing', 'reviewing', 'complete']

  return (
    <div className="h-full flex flex-col">
      {/* Navigation Tabs with Project Name and Actions */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          {/* Left: Navigation Tabs */}
          <nav className="-mb-px flex space-x-8 shrink-0">
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

          {/* Center: Project Name and Description (inline) */}
          <div className="flex-1 min-w-0 flex items-center justify-center gap-2 py-1">
            <h1 className={`text-xl font-bold ${textColors.primary} truncate shrink-0`}>
              {project?.name}
            </h1>

            {!descriptionField.isEditing ? (
              <div
                className="flex items-center gap-1 group cursor-pointer min-w-0"
                onClick={descriptionField.startEditing}
              >
                <span className={`text-sm ${textColors.secondary} shrink-0`}>&mdash;</span>
                {project?.description ? (
                  <p className={`text-sm ${textColors.secondary} truncate`}>
                    {project.description}
                  </p>
                ) : (
                  <p className={`text-sm ${textColors.secondary} italic opacity-60 truncate`}>
                    Add a description...
                  </p>
                )}
                <Button
                  onClick={(e) => { e.stopPropagation(); descriptionField.startEditing() }}
                  variant="ghost"
                  size="sm"
                  className="p-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                  title="Edit description"
                >
                  <PencilIcon className="w-3 h-3" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Input
                  value={descriptionField.editedValue}
                  onChange={(e) => descriptionField.setEditedValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') descriptionField.save()
                    if (e.key === 'Escape') descriptionField.cancelEditing()
                  }}
                  placeholder="Enter project description..."
                  className="text-sm w-80"
                  maxLength={300}
                  autoFocus
                />
                <Button
                  onClick={descriptionField.save}
                  variant="secondary"
                  size="sm"
                  className="p-1.5 min-w-[28px] h-7 border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400 dark:bg-green-900/30 dark:border-green-700 dark:text-green-400"
                  title="Save (Enter)"
                  loading={descriptionField.saving}
                >
                  <CheckIcon className="w-4 h-4" />
                </Button>
                <Button
                  onClick={descriptionField.cancelEditing}
                  variant="secondary"
                  size="sm"
                  className="p-1.5 min-w-[28px] h-7 border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-400"
                  title="Cancel (Escape)"
                >
                  <XMarkIcon className="w-4 h-4" />
                </Button>
              </div>
            )}
            {descriptionField.error && (
              <p className="text-xs text-red-500">{descriptionField.error}</p>
            )}
          </div>

          {/* Right: Actions */}
          <div className="flex items-center shrink-0">
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
        <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6 flex-1 min-h-0 overflow-hidden">
          {/* Left Side - Project Specification */}
          <div className="flex flex-col overflow-hidden">
            {/* Specification Document Section */}
            <Card padding="xs" className="h-full flex flex-col overflow-hidden">
              <div className="flex items-center justify-between mb-2 flex-shrink-0">
                <h3 className={`text-lg font-medium ${textColors.primary}`}>Project Context</h3>
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
                    {specificationDoc?.content ? (
                      <Markdown>{specificationDoc.content}</Markdown>
                    ) : (
                      <p className="text-gray-500 dark:text-gray-400 italic">No project context provided. Click Edit to add context.</p>
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
            onConversationReset={handleConversationReset}
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