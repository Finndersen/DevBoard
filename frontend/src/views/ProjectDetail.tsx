import { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeftIcon, PlusIcon, PencilIcon, CheckIcon, ChatBubbleLeftIcon, XMarkIcon, CodeBracketIcon, ListBulletIcon } from '@heroicons/react/24/outline'
import AgentChat from '../components/chat/AgentChat'
import ProjectConversationSelector from '../components/chat/ProjectConversationSelector'
import CreateCodebaseModal from '../components/modals/CreateCodebaseModal'
import { Button, Card, Input } from '../components/ui'
import { MarkdownDocumentEditor } from '../components/MarkdownDocumentEditor'
import { textColors, borderColors, layouts, loadingSpinner } from '../styles/designSystem'
import { apiClient } from '../lib/api'
import type { Codebase, CustomFieldDefinition } from '../lib/api'
import { useModal, useEditableField, useProject, useProjectCodebases, useLinkCodebaseToProject, useUnlinkCodebaseFromProject, useDocument } from '../hooks'
import { useCodebases } from '../hooks/useCodebases'
import { useViewTitle } from '../hooks/useViewTitle'
import { useToolResultHandler } from '../hooks/useConversationEventHandlers'
import { useDataStore } from '../stores/dataStore'
import { useUIStore } from '../stores/uiStore'
import { useConversationStore } from '../stores/conversationStore'
import { useConversationStreamStore } from '../stores/conversationStreamStore'
import { useNotificationStore } from '../stores/notificationStore'
import { reportMutationError } from '../lib/errors'
import { CustomFieldsPopover } from '../components/common/CustomFieldsPanel'
import ChatDetailLayout from '../components/layout/ChatDetailLayout'
import AgentActionBar from '../components/layout/AgentActionBar'
import type { AgentChatHandle } from '../components/chat/AgentChat'

interface ProjectDetailProps {
  id: string
}

function ProjectDetail({ id }: ProjectDetailProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { setProject: setStoreProject } = useDataStore()
  const { addNotification } = useNotificationStore()
  const removeConversation = useConversationStore(s => s.removeConversation)

  // Update tab title when project data is loaded
  useViewTitle('project', id)

  // Fetch data using hooks
  const { data: project, loading: projectLoading, refetch: refetchProject, setData: setProject } = useProject(id!)

  // Fetch specification document separately - only when project is loaded with valid document ID
  const { data: specificationDoc, refetch: refetchSpecification } = useDocument(project?.specification_document_id ?? null)

  // Project codebases hooks
  const { data: projectCodebases, loading: codebasesLoading, refetch: refetchProjectCodebases } = useProjectCodebases(id!)
  const { data: allCodebases, refetch: refetchAllCodebases } = useCodebases()
  const { mutate: linkCodebase, loading: linkingCodebase } = useLinkCodebaseToProject()
  const { mutate: unlinkCodebase, loading: unlinkingCodebase } = useUnlinkCodebaseFromProject()

  // Ref to AgentChat for sending messages
  const agentChatRef = useRef<AgentChatHandle>(null)

  // Active conversation management — initialize from URL param if present
  const [activeConversationId, setActiveConversationId] = useState<number | null>(() => {
    const params = new URLSearchParams(window.location.search)
    const conversationParam = params.get('conversation')
    return conversationParam ? parseInt(conversationParam, 10) : null
  })

  // State for codebase linking UI
  const [selectedCodebaseToLink, setSelectedCodebaseToLink] = useState<string>('')
  const createCodebaseModal = useModal()

  // Combined loading state
  const loading = projectLoading

  // Get tab from URL query params, default to 'home'
  const getTabFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search)
    const tab = params.get('tab') as 'home' | 'settings'
    return ['home', 'settings'].includes(tab) ? tab : 'home'
  }, [location.search])

  const [activeTab, setActiveTab] = useState<'editor' | 'settings'>(() => {
    const tab = getTabFromUrl()
    return tab === 'settings' ? 'settings' : 'editor'
  })

  // Get UI store actions
  const { createAndOpenDraft, invalidateConversations } = useUIStore()

  // Use new custom hooks
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
  const handleTabChange = (tab: 'editor' | 'settings') => {
    setActiveTab(tab)
    const urlTab = tab === 'editor' ? 'home' : tab
    const params = new URLSearchParams(location.search)
    params.set('tab', urlTab)
    navigate(`/projects/${id}?${params.toString()}`, { replace: true })
  }

  // Update activeTab when URL changes
  useEffect(() => {
    const urlTab = getTabFromUrl()
    setActiveTab(urlTab === 'settings' ? 'settings' : 'editor')
  }, [getTabFromUrl])

  const updateConversationUrl = useCallback((conversationId: number | null) => {
    const params = new URLSearchParams(location.search)
    if (conversationId !== null) {
      params.set('conversation', String(conversationId))
    } else {
      params.delete('conversation')
    }
    navigate(`/projects/${id}?${params.toString()}`, { replace: true })
  }, [location.search, navigate, id])

  // Sync URL conversation param -> state (handles clicking a conversation in the panel while already on this project)
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const urlConversationId = params.get('conversation')
    if (urlConversationId) {
      setActiveConversationId(parseInt(urlConversationId, 10))
    }
  }, [location.search])

  // Store project in DataStore when loaded
  useEffect(() => {
    if (project) {
      setStoreProject(project)
    }
  }, [project, setStoreProject])

  // Initialize active conversation from project data (fallback when no URL param)
  useEffect(() => {
    const urlHasConversation = new URLSearchParams(location.search).has('conversation')
    if (project?.default_conversation_id && activeConversationId === null && !urlHasConversation) {
      const defaultId = project.default_conversation_id
      setActiveConversationId(defaultId)
      const params = new URLSearchParams(location.search)
      params.set('conversation', String(defaultId))
      navigate(`/projects/${id}?${params.toString()}`, { replace: true })
    }
  }, [project?.default_conversation_id, activeConversationId, location.search, navigate, id])

  // Custom fields state
  const [customFieldDefinitions, setCustomFieldDefinitions] = useState<CustomFieldDefinition[]>([])
  const [customFieldSaving, setCustomFieldSaving] = useState(false)

  useEffect(() => {
    apiClient.getCustomFieldDefinitions('project')
      .then(setCustomFieldDefinitions)
      .catch(err => console.error('Failed to load project custom field definitions:', err))
  }, [])

  const handleCustomFieldChange = useCallback(async (fieldName: string, value: unknown) => {
    if (!project) return
    setCustomFieldSaving(true)
    try {
      await apiClient.updateProject(id!, { custom_fields: { [fieldName]: value } })
      await refetchProject()
    } catch (err) {
      reportMutationError(addNotification, err, {
        entityType: 'project',
        entityId: id ?? null,
        entityTitle: project?.name ?? null,
        fallbackMessage: `Failed to update custom field "${fieldName}"`,
      })
    } finally {
      setCustomFieldSaving(false)
    }
  }, [project, id, refetchProject, addNotification])

  // Handle project specification updates from MCP tools during stream processing
  const projectSpecificationHandler = useCallback(async (toolName: string) => {
    if (
      toolName.includes('edit_project_specification') ||
      toolName.includes('set_project_specification_content')
    ) {
      try {
        await refetchSpecification()
      } catch (error) {
        console.error('Failed to refetch project specification document:', error)
      }
    }
  }, [refetchSpecification])

  useToolResultHandler(projectSpecificationHandler)

  // Layout state
  const isNarrowRef = useRef(false)
  const handleNarrowChange = useCallback((narrow: boolean) => { isNarrowRef.current = narrow }, [])
  const expandedPanel = useUIStore(s => s.expandedPanel)
  const setExpandedPanel = useUIStore(s => s.setExpandedPanel)

  // Chat streaming state
  const isStreaming = useConversationStreamStore(
    s => activeConversationId ? s.isConversationStreaming(activeConversationId) : false
  )

  // Chat activity indicator
  const [chatNeedsAttention, setChatNeedsAttention] = useState(false)
  const prevStreamingRef = useRef(isStreaming)

  useEffect(() => {
    if (prevStreamingRef.current && !isStreaming && isNarrowRef.current && expandedPanel === 'details') {
      setChatNeedsAttention(true)
    }
    prevStreamingRef.current = isStreaming
  }, [isStreaming, expandedPanel])

  useEffect(() => {
    if (expandedPanel === 'chat') {
      setChatNeedsAttention(false)
    }
  }, [expandedPanel])

  // Details content change detection
  const [detailsNeedsAttention, setDetailsNeedsAttention] = useState(false)
  const prevDetailsDataRef = useRef<string>('')

  useEffect(() => {
    const dataFingerprint = specificationDoc?.content ?? ''
    if (prevDetailsDataRef.current && dataFingerprint !== prevDetailsDataRef.current) {
      if (isNarrowRef.current && expandedPanel === 'chat') {
        setDetailsNeedsAttention(true)
      }
    }
    prevDetailsDataRef.current = dataFingerprint
  }, [specificationDoc?.content, expandedPanel])

  useEffect(() => {
    if (expandedPanel === 'details') {
      setDetailsNeedsAttention(false)
    }
  }, [expandedPanel])

  // Handle creating a new project conversation using draft system
  const handleNewConversation = useCallback(() => {
    if (!project) return
    createAndOpenDraft('project_conversation', { projectId: project.id.toString() })
  }, [project, createAndOpenDraft])

  // Handle creating a new task using draft system
  const handleCreateTask = useCallback(() => {
    if (!project) return
    createAndOpenDraft('task', { selectedProjectId: project.id.toString() })
  }, [project, createAndOpenDraft])

  // Handle switching conversations
  const handleSelectConversation = useCallback((conversationId: number) => {
    setActiveConversationId(conversationId)
    updateConversationUrl(conversationId)
  }, [updateConversationUrl])

  // Handle deleting a conversation
  const handleDeleteConversation = useCallback(async (conversationId: number) => {
    try {
      await apiClient.deleteConversation(conversationId)
      removeConversation(conversationId)
      invalidateConversations()
      // If we deleted the active conversation, switch to most recent
      if (conversationId === activeConversationId) {
        // Refetch project to get the new default
        const updatedProject = await apiClient.getProject(id!)
        setProject(updatedProject)
        setActiveConversationId(updatedProject.default_conversation_id)
        updateConversationUrl(updatedProject.default_conversation_id)
      }
    } catch (error) {
      reportMutationError(addNotification, error, {
        entityType: 'project',
        entityId: id ?? null,
        entityTitle: project?.name ?? null,
        fallbackMessage: 'Failed to delete conversation',
      })
    }
  }, [activeConversationId, id, addNotification, setProject, updateConversationUrl, removeConversation, invalidateConversations, project])

  // Handle renaming a conversation
  const handleRenameConversation = useCallback(async (conversationId: number, title: string) => {
    try {
      await apiClient.updateConversationTitle(conversationId, title)
    } catch (error) {
      reportMutationError(addNotification, error, {
        entityType: 'project',
        entityId: id ?? null,
        entityTitle: project?.name ?? null,
        fallbackMessage: 'Failed to rename conversation',
      })
    }
  }, [addNotification, id, project])

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
      reportMutationError(addNotification, error, {
        entityType: 'project',
        entityId: id ?? null,
        entityTitle: project?.name ?? null,
        fallbackMessage: 'Failed to link codebase',
      })
    }
  }, [selectedCodebaseToLink, id, linkCodebase, refetchProjectCodebases, addNotification, project])

  // Handle unlinking a codebase from the project
  const handleUnlinkCodebase = useCallback(async (codebaseId: number) => {
    try {
      await unlinkCodebase({ projectId: id!, codebaseId })
      await refetchProjectCodebases()
    } catch (error) {
      reportMutationError(addNotification, error, {
        entityType: 'project',
        entityId: id ?? null,
        entityTitle: project?.name ?? null,
        fallbackMessage: 'Failed to unlink codebase',
      })
    }
  }, [id, unlinkCodebase, refetchProjectCodebases, addNotification, project])

  // Handle new codebase created - link it to the project
  const handleCodebaseCreated = useCallback(async (codebase: Codebase) => {
    try {
      await linkCodebase({ projectId: id!, codebaseId: codebase.id })
      await refetchProjectCodebases()
      await refetchAllCodebases()
    } catch (error) {
      reportMutationError(addNotification, error, {
        entityType: 'project',
        entityId: id ?? null,
        entityTitle: project?.name ?? null,
        fallbackMessage: 'Failed to link newly created codebase',
      })
    }
  }, [id, linkCodebase, refetchProjectCodebases, refetchAllCodebases, addNotification, project])

  // Panel switching callbacks
  // (removed handleSendMessage - chat no longer auto-expands on message send)

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

  return (
    <div className="h-full flex flex-col">
      {/* Navigation Tabs with Project Name and Actions */}
      <div className={`border-b ${borderColors.default} mb-4 flex-shrink-0`}>
        <div className="flex items-center justify-between">
          {/* Left: Navigation Tabs */}
          <nav className="-mb-px flex space-x-8 shrink-0">
            {[
              { id: 'editor' as const, name: 'Home', icon: ChatBubbleLeftIcon },
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
          <div className="flex items-center gap-2 shrink-0">
            <CustomFieldsPopover
              customFields={project.custom_fields}
              fieldDefinitions={customFieldDefinitions}
              onFieldChange={handleCustomFieldChange}
              saving={customFieldSaving}
            />
            <Button onClick={() => navigate(`/tasks?project_id=${id}`)} variant="outline" size="sm">
              <ListBulletIcon className="w-4 h-4 mr-2" />
              View Tasks
            </Button>
            <Button onClick={handleCreateTask} size="sm">
              <PlusIcon className="w-4 h-4 mr-2" />
              New Task
            </Button>
          </div>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'editor' && (
        <ChatDetailLayout
          expandedPanel={expandedPanel}
          onNarrowChange={handleNarrowChange}
          onExpandPanel={(panel) => setExpandedPanel(panel)}
          chatStripProps={{
            isStreaming: isStreaming,
            needsAttention: chatNeedsAttention,
          }}
          detailsStripProps={{
            needsAttention: detailsNeedsAttention,
          }}
          chatContent={
            <AgentChat
              ref={agentChatRef}
              conversationId={activeConversationId}
              emptyStateMessage="Ask me anything about this project!"
              className="h-full flex flex-col overflow-hidden"
              conversationSelector={
                activeConversationId ? (
                  <ProjectConversationSelector
                    projectId={project.id}
                    activeConversationId={activeConversationId}
                    onSelect={handleSelectConversation}
                    onNew={handleNewConversation}
                    onDelete={handleDeleteConversation}
                    onRename={handleRenameConversation}
                  />
                ) : undefined
              }
              onNewConversation={handleNewConversation}
            />
          }
          detailsContent={
            <Card padding="xs" className="h-full flex flex-col overflow-hidden">
              <h3 className={`text-lg font-medium ${textColors.primary} mb-2 flex-shrink-0`}>Project Context</h3>
              <div className="flex-1 overflow-hidden flex flex-col">
                <MarkdownDocumentEditor
                  content={specificationDoc?.content}
                  field={specificationField}
                  placeholder="Enter project specification in Markdown format..."
                  emptyText="No project context provided."
                  textareaClassName="w-full font-mono text-sm"
                />
              </div>
            </Card>
          }
          actionBar={
            <AgentActionBar
              conversationId={activeConversationId}
              isStreaming={isStreaming}
              onStopStream={() => agentChatRef.current?.stopStream()}
              isDisabled={agentChatRef.current?.sessionExpired ?? false}
              disabledMessage="Session expired - please refresh"
              placeholder="Ask a question about this project..."
            />
          }
        />
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
                  className={`flex-1 px-3 py-2 border ${borderColors.input} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-white/[0.06] ${textColors.primary}`}
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
                    className={`flex items-center justify-between p-3 bg-white dark:bg-white/[0.06] border ${borderColors.input} rounded-lg`}
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