import { useState, useCallback, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Modal, Button, Input, Textarea } from '../ui'
import Alert from '../ui/Alert'
import { apiClient } from '../../lib/api'
import type { Codebase, CustomFieldDefinition } from '../../lib/api'
import { useProjects, useProjectCodebases } from '../../hooks'
import { useDataStore } from '../../stores/dataStore'
import { useUIStore } from '../../stores/uiStore'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { CustomFieldInputs } from '../common/CustomFieldInputs'

interface CreateTaskModalProps {
  draftId: string
  onClose: () => void
  projectId?: string
}

export default function CreateTaskModal({ draftId, onClose, projectId }: CreateTaskModalProps) {
  const navigate = useNavigate()
  const { data: projects } = useProjects()
  const { setTask, fetchProjectTasks } = useDataStore()
  const { modalDrafts, openModalDraft, saveModalDraft, removeModalDraft, setOpenModalDraft } = useUIStore()
  const { seedInitialMessage } = useConversationStreamStore()

  const isOpen = openModalDraft === draftId
  const currentDraft = modalDrafts[draftId]

  // Initialize form data from draft or defaults
  const initializeFormData = useCallback(() => {
    const draftData = currentDraft?.formData
    return {
      title: (draftData?.title as string) || '',
      codebase_id: (draftData?.codebase_id as number) || null,
      working_branch: (draftData?.working_branch as string) || '',
      base_branch: (draftData?.base_branch as string) || '',
      initial_message: (draftData?.initial_message as string) || '',
      selectedProjectId: (draftData?.selectedProjectId as string) || projectId || '',
      autoGenerateBranch: (draftData?.autoGenerateBranch as boolean) ?? true,
      customFieldValues: (draftData?.customFieldValues as Record<string, unknown>) || {},
      autoSelectModel: (draftData?.autoSelectModel as boolean) ?? true,
      model_type: (draftData?.model_type as string) || ''
    }
  }, [currentDraft?.formData, projectId])

  const [formData, setFormData] = useState(initializeFormData)
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Fetch codebases for selected project
  const { data: codebases, loading: codebasesLoading, refetch: refetchCodebases } = useProjectCodebases(formData.selectedProjectId || '0')

  // Custom fields state
  const [customFieldDefinitions, setCustomFieldDefinitions] = useState<CustomFieldDefinition[]>([])
  const [customFieldsLoading, setCustomFieldsLoading] = useState(false)

  // Agent configuration state
  const [agentConfig, setAgentConfig] = useState<{ model_type?: string; model_type_display_names?: Record<string, string> } | null>(null)
  const [agentConfigLoading, setAgentConfigLoading] = useState(false)

  // Auto-save draft
  const saveDraft = useCallback(() => {
    const previewLabel = formData.initial_message?.slice(0, 30) || formData.title?.slice(0, 30) || 'New Task'
    saveModalDraft(draftId, {
      type: 'task',
      formData,
      previewLabel,
      createdAt: Date.now()
    })
  }, [draftId, formData, saveModalDraft])

  // Debounced save
  useEffect(() => {
    const timer = setTimeout(saveDraft, 300)
    return () => clearTimeout(timer)
  }, [saveDraft])

  // Reset form data when draft changes (e.g., when opening a different draft)
  useEffect(() => {
    setFormData(initializeFormData())
  }, [initializeFormData])

  // Refetch codebases when selected project changes
  useEffect(() => {
    if (isOpen && formData.selectedProjectId) {
      refetchCodebases()
    }
  }, [isOpen, formData.selectedProjectId, refetchCodebases])

  // Fetch custom fields when modal opens
  useEffect(() => {
    if (isOpen) {
      setCustomFieldsLoading(true)
      apiClient.getCustomFieldDefinitions('task')
        .then(fields => {
          setCustomFieldDefinitions(fields)
          // Only initialize custom field values if they don't exist in the draft
          if (!currentDraft?.formData?.customFieldValues || Object.keys(currentDraft.formData.customFieldValues).length === 0) {
            const initialValues: Record<string, unknown> = {}
            fields.forEach(field => {
              if (field.type === 'boolean') {
                initialValues[field.name] = false
              } else {
                initialValues[field.name] = ''
              }
            })
            setFormData(prev => ({ ...prev, customFieldValues: initialValues }))
          }
        })
        .catch(err => console.error('Failed to load custom fields:', err))
        .finally(() => setCustomFieldsLoading(false))
    }
  }, [isOpen, currentDraft?.formData?.customFieldValues])

  // Fetch agent configuration when modal opens (run only once per open, not on every draft save)
  useEffect(() => {
    if (isOpen) {
      setAgentConfigLoading(true)
      apiClient.getAgentConfiguration('task_planning')
        .then(config => {
          const defaultModelType = config.config.model?.model_type || 'standard'
          setAgentConfig({
            model_type: defaultModelType,
            model_type_display_names: config.model_type_display_names
          })
          // Set default model_type in form if not already set in draft
          if (!currentDraft?.formData?.model_type) {
            setFormData(prev => ({ ...prev, model_type: defaultModelType }))
          }
        })
        .catch(err => console.error('Failed to load agent configuration:', err))
        .finally(() => setAgentConfigLoading(false))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  // Reset error state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setIsCreating(false)
      setCreateError(null)
    }
  }, [isOpen])

  const handleProjectChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({
      ...prev,
      selectedProjectId: e.target.value,
      codebase_id: null,
      base_branch: ''
    }))
  }, [])

  const handleTaskTitleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, title: e.target.value }))
  }, [])

  const handleTaskCodebaseChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const codebaseId = e.target.value ? Number(e.target.value) : null
    const selectedCodebase = codebaseId && codebases
      ? codebases.find((c: Codebase) => c.id === codebaseId)
      : null
    setFormData(prev => ({
      ...prev,
      codebase_id: codebaseId,
      base_branch: selectedCodebase?.default_branch || ''
    }))
  }, [codebases])

  const handleWorkingBranchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, working_branch: e.target.value }))
  }, [])

  const handleBaseBranchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, base_branch: e.target.value }))
  }, [])

  const handleInitialMessageChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFormData(prev => ({ ...prev, initial_message: e.target.value }))
  }, [])

  const handleAutoGenerateChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const isChecked = e.target.checked
    setFormData(prev => ({
      ...prev,
      autoGenerateBranch: isChecked,
      working_branch: isChecked ? '' : prev.working_branch
    }))
  }, [])

  const handleAutoSelectModelChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({
      ...prev,
      autoSelectModel: e.target.checked
    }))
  }, [])

  const handleModelTypeChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData(prev => ({
      ...prev,
      model_type: e.target.value
    }))
  }, [])

  const handleCustomFieldChange = useCallback((fieldName: string, value: unknown) => {
    setFormData(prev => ({
      ...prev,
      customFieldValues: { ...prev.customFieldValues, [fieldName]: value }
    }))
  }, [])

  const areMandatoryFieldsFilled = useCallback(() => {
    const mandatoryFields = customFieldDefinitions.filter(f => f.mandatory)
    return mandatoryFields.every(field => {
      const value = formData.customFieldValues[field.name]
      return value !== undefined && value !== null && value !== ''
    })
  }, [customFieldDefinitions, formData.customFieldValues])

  const effectiveProjectId = projectId ?? formData.selectedProjectId

  // Minimize handler - saves draft and hides modal
  const handleMinimize = useCallback(() => {
    saveDraft()
    setOpenModalDraft(null)
  }, [saveDraft, setOpenModalDraft])

  // Close handler - removes draft and hides modal
  const handleClose = useCallback(() => {
    removeModalDraft(draftId)
    onClose()
  }, [draftId, removeModalDraft, onClose])

  const handleCreateTask = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!effectiveProjectId) return
    setIsCreating(true)
    setCreateError(null)
    try {
      const customFields: Record<string, unknown> = {}
      Object.entries(formData.customFieldValues).forEach(([name, value]) => {
        if (value !== '' && value !== null && value !== undefined) {
          customFields[name] = value
        }
      })

      const taskData: Record<string, unknown> = {
        codebase_id: formData.codebase_id,
        specification_content: null,
        custom_fields: Object.keys(customFields).length > 0 ? customFields : null
      }

      // Only include title if provided
      if (formData.title?.trim()) {
        taskData.title = formData.title.trim()
      }

      // Include initial_message if provided
      if (formData.initial_message?.trim()) {
        taskData.initial_message = formData.initial_message.trim()
      }

      if (formData.working_branch.trim()) {
        taskData.branch_name = formData.working_branch.trim()
      }

      if (formData.base_branch.trim()) {
        taskData.base_branch = formData.base_branch.trim()
      }

      // Include model_type based on auto-select setting
      if (formData.autoSelectModel && formData.initial_message?.trim()) {
        taskData.model_type = 'auto'
      } else if (formData.model_type) {
        taskData.model_type = formData.model_type
      }

      const createdTask = await apiClient.createTask(effectiveProjectId, taskData)

      setTask(createdTask)
      await fetchProjectTasks(effectiveProjectId)

      // Seed initial user message into stream store if provided
      if (formData.initial_message?.trim() && createdTask.conversation_id) {
        seedInitialMessage(createdTask.conversation_id, formData.initial_message.trim())
      }

      // Remove the draft and close modal on success
      removeModalDraft(draftId)
      onClose()

      // Navigate to task details
      navigate(`/tasks/${createdTask.id}`)
    } catch (error) {
      console.error('Failed to create task:', error)
      setCreateError(error instanceof Error ? error.message : 'Failed to create task')
    } finally {
      setIsCreating(false)
    }
  }, [formData, effectiveProjectId, navigate, onClose, setTask, fetchProjectTasks, draftId, removeModalDraft, seedInitialMessage])

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={
        <div className="flex items-center justify-between">
          <span>Create New Task</span>
          <button
            type="button"
            onClick={handleMinimize}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors ml-2"
            title="Minimize to draft"
            aria-label="Minimize to draft"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>
        </div>
      }
      maxWidth="xl"
    >
      <form onSubmit={handleCreateTask} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Initial Prompt
          </label>
          <Textarea
            value={formData.initial_message}
            onChange={handleInitialMessageChange}
            placeholder="Describe what you want to do with this task, including as much detail and context as possible. This will be used to start the conversation with the AI assistant."
            rows={6}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Task Title (Optional)
          </label>
          <Input
            type="text"
            value={formData.title}
            onChange={handleTaskTitleChange}
            placeholder="Auto-generated from prompt if empty"
          />
        </div>

        {/* Project Selection - only when no projectId prop */}
        {!projectId && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Project
            </label>
            <select
              value={formData.selectedProjectId}
              onChange={handleProjectChange}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white"
              required
            >
              <option value="">Select a project...</option>
              {projects?.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Codebase and Base Branch - only show when project is selected */}
        {formData.selectedProjectId && (
          <div className="grid grid-cols-4 gap-4">
            <div className="col-span-3">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Codebase
              </label>
              {codebasesLoading ? (
                <div className="text-sm text-gray-500 dark:text-gray-400">Loading codebases...</div>
              ) : !codebases || codebases.length === 0 ? (
                <Alert variant="warning">
                  <p className="mb-2">No codebases are linked to this project.</p>
                  <p>
                    Please{' '}
                    <Link
                      to={`/projects/${formData.selectedProjectId}?tab=settings`}
                      onClick={onClose}
                      className="font-medium underline hover:opacity-80"
                    >
                      link a codebase in project settings
                    </Link>
                    {' '}before creating a task.
                  </p>
                </Alert>
              ) : (
                <select
                  value={formData.codebase_id ?? ''}
                  onChange={handleTaskCodebaseChange}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white"
                  required
                >
                  <option value="">Select a codebase</option>
                  {codebases.map((codebase) => (
                    <option key={codebase.id} value={codebase.id}>
                      {codebase.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {formData.codebase_id && (
              <div className="col-span-1">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Base Branch
                </label>
                <Input
                  type="text"
                  value={formData.base_branch}
                  onChange={handleBaseBranchChange}
                  placeholder="origin/main"
                />
              </div>
            )}
          </div>
        )}

        {/* Working Branch Configuration */}
        {formData.codebase_id && (
          <div>
            <div className="flex items-center mb-2">
              <input
                type="checkbox"
                id="auto-generate-branch"
                checked={formData.autoGenerateBranch}
                onChange={handleAutoGenerateChange}
                className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="auto-generate-branch" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Auto-generate working branch
              </label>
            </div>
            {!formData.autoGenerateBranch && (
              <Input
                type="text"
                value={formData.working_branch}
                onChange={handleWorkingBranchChange}
                placeholder="custom-branch-name"
              />
            )}
          </div>
        )}

        {/* Agent Model Configuration */}
        {formData.codebase_id && (
          <div>
            {formData.initial_message?.trim() && (
              <div className="flex items-center mb-2">
                <input
                  type="checkbox"
                  id="auto-select-model"
                  checked={formData.autoSelectModel}
                  onChange={handleAutoSelectModelChange}
                  className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="auto-select-model" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Auto-select from prompt
                </label>
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Agent Model
              </label>
              <select
                value={formData.model_type}
                onChange={handleModelTypeChange}
                disabled={!!(formData.autoSelectModel && formData.initial_message?.trim())}
                className={`w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-white/[0.06] text-gray-900 dark:text-white ${
                  formData.autoSelectModel && formData.initial_message?.trim() ? 'opacity-60 cursor-not-allowed' : ''
                }`}
              >
                {agentConfigLoading ? (
                  <option>Loading models...</option>
                ) : (
                  <>
                    <option value="fast">
                      Fast{agentConfig?.model_type_display_names?.fast ? ` (${agentConfig.model_type_display_names.fast})` : ''}
                    </option>
                    <option value="standard">
                      Standard{agentConfig?.model_type_display_names?.standard ? ` (${agentConfig.model_type_display_names.standard})` : ''}
                    </option>
                    <option value="advanced">
                      Advanced{agentConfig?.model_type_display_names?.advanced ? ` (${agentConfig.model_type_display_names.advanced})` : ''}
                    </option>
                  </>
                )}
              </select>
              {formData.model_type && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {formData.model_type === 'fast' && 'Trivial/mechanical changes only'}
                  {formData.model_type === 'standard' && 'Moderate complexity'}
                  {formData.model_type === 'advanced' && 'Complex/architectural changes'}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Custom Fields */}
        <CustomFieldInputs
          definitions={customFieldDefinitions}
          values={formData.customFieldValues}
          onChange={handleCustomFieldChange}
          loading={customFieldsLoading}
        />

        {createError && <Alert variant="error">{createError}</Alert>}

        <div className="flex justify-end space-x-3 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            disabled={isCreating}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={isCreating}
            disabled={(!formData.title.trim() && !formData.initial_message.trim()) || !formData.codebase_id || !formData.selectedProjectId || isCreating || !areMandatoryFieldsFilled()}
          >
            Create Task
          </Button>
        </div>
      </form>
    </Modal>
  )
}
