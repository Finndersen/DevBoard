import { useState, useCallback, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Modal, Button, Input, Textarea } from '../ui'
import Alert from '../ui/Alert'
import { apiClient } from '../../lib/api'
import type { Codebase, CustomFieldDefinition } from '../../lib/api'
import { useProjects, useProjectCodebases } from '../../hooks'
import { useDataStore } from '../../stores/dataStore'
import { CustomFieldInputs } from '../common/CustomFieldInputs'

interface CreateTaskModalProps {
  isOpen: boolean
  onClose: () => void
  projectId?: string
}

export default function CreateTaskModal({ isOpen, onClose, projectId }: CreateTaskModalProps) {
  const navigate = useNavigate()
  const { data: projects } = useProjects()
  const { setTask, fetchProjectTasks } = useDataStore()

  // Selected project (from prop or user selection)
  const [selectedProjectId, setSelectedProjectId] = useState<string>(projectId ?? '')

  // Fetch codebases for selected project
  const { data: codebases, loading: codebasesLoading, refetch: refetchCodebases } = useProjectCodebases(selectedProjectId || '0')

  const [newTask, setNewTask] = useState({
    title: '',
    codebase_id: null as number | null,
    working_branch: '',
    base_branch: '',
    initial_message: ''
  })
  const [isCreating, setIsCreating] = useState(false)
  const [autoGenerateBranch, setAutoGenerateBranch] = useState(true)

  // Custom fields state
  const [customFieldDefinitions, setCustomFieldDefinitions] = useState<CustomFieldDefinition[]>([])
  const [customFieldValues, setCustomFieldValues] = useState<Record<string, unknown>>({})
  const [customFieldsLoading, setCustomFieldsLoading] = useState(false)

  // Update selected project when prop changes
  useEffect(() => {
    if (projectId) {
      setSelectedProjectId(projectId)
    }
  }, [projectId])

  // Refetch codebases when selected project changes
  useEffect(() => {
    if (isOpen && selectedProjectId) {
      refetchCodebases()
    }
  }, [isOpen, selectedProjectId, refetchCodebases])

  // Fetch custom fields when modal opens
  useEffect(() => {
    if (isOpen) {
      setCustomFieldsLoading(true)
      apiClient.getCustomFieldDefinitions('task')
        .then(fields => {
          setCustomFieldDefinitions(fields)
          const initialValues: Record<string, unknown> = {}
          fields.forEach(field => {
            if (field.type === 'boolean') {
              initialValues[field.name] = false
            } else {
              initialValues[field.name] = ''
            }
          })
          setCustomFieldValues(initialValues)
        })
        .catch(err => console.error('Failed to load custom fields:', err))
        .finally(() => setCustomFieldsLoading(false))
    }
  }, [isOpen])

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setNewTask({
        title: '',
        codebase_id: null,
        working_branch: '',
        base_branch: '',
        initial_message: ''
      })
      setIsCreating(false)
      setAutoGenerateBranch(true)
      setCustomFieldValues({})
      if (!projectId) {
        setSelectedProjectId('')
      }
    }
  }, [isOpen, projectId])

  const handleProjectChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedProjectId(e.target.value)
    // Reset codebase selection when project changes
    setNewTask(prev => ({ ...prev, codebase_id: null, base_branch: '' }))
  }, [])

  const handleTaskTitleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewTask(prev => ({ ...prev, title: e.target.value }))
  }, [])

  const handleTaskCodebaseChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const codebaseId = e.target.value ? Number(e.target.value) : null
    const selectedCodebase = codebaseId && codebases
      ? codebases.find((c: Codebase) => c.id === codebaseId)
      : null
    setNewTask(prev => ({
      ...prev,
      codebase_id: codebaseId,
      base_branch: selectedCodebase?.default_branch || ''
    }))
  }, [codebases])

  const handleWorkingBranchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewTask(prev => ({ ...prev, working_branch: e.target.value }))
  }, [])

  const handleBaseBranchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewTask(prev => ({ ...prev, base_branch: e.target.value }))
  }, [])

  const handleInitialMessageChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewTask(prev => ({ ...prev, initial_message: e.target.value }))
  }, [])

  const handleAutoGenerateChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const isChecked = e.target.checked
    setAutoGenerateBranch(isChecked)
    if (isChecked) {
      setNewTask(prev => ({ ...prev, working_branch: '' }))
    }
  }, [])

  const handleCustomFieldChange = useCallback((fieldName: string, value: unknown) => {
    setCustomFieldValues(prev => ({ ...prev, [fieldName]: value }))
  }, [])

  const areMandatoryFieldsFilled = useCallback(() => {
    const mandatoryFields = customFieldDefinitions.filter(f => f.mandatory)
    return mandatoryFields.every(field => {
      const value = customFieldValues[field.name]
      return value !== undefined && value !== null && value !== ''
    })
  }, [customFieldDefinitions, customFieldValues])

  const effectiveProjectId = projectId ?? selectedProjectId

  const handleCreateTask = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!effectiveProjectId) return
    setIsCreating(true)
    try {
      const customFields: Record<string, unknown> = {}
      Object.entries(customFieldValues).forEach(([name, value]) => {
        if (value !== '' && value !== null && value !== undefined) {
          customFields[name] = value
        }
      })

      const taskData: any = {
        title: newTask.title,
        codebase_id: newTask.codebase_id,
        specification_content: null,
        custom_fields: Object.keys(customFields).length > 0 ? customFields : null
      }

      if (newTask.working_branch.trim()) {
        taskData.branch_name = newTask.working_branch.trim()
      }

      if (newTask.base_branch.trim()) {
        taskData.base_branch = newTask.base_branch.trim()
      }

      const createdTask = await apiClient.createTask(effectiveProjectId, taskData)

      setTask(createdTask)
      await fetchProjectTasks(effectiveProjectId)

      const initialMessage = newTask.initial_message.trim() || null

      setNewTask({
        title: '',
        codebase_id: null,
        working_branch: '',
        base_branch: '',
        initial_message: ''
      })

      onClose()
      navigate(`/tasks/${createdTask.id}`, {
        state: initialMessage ? { initialMessage, taskId: createdTask.id } : undefined
      })
    } catch (error) {
      console.error('Failed to create task:', error)
    } finally {
      setIsCreating(false)
    }
  }, [newTask, effectiveProjectId, navigate, onClose, setTask, fetchProjectTasks, customFieldValues])

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Task"
      maxWidth="xl"
    >
      <form onSubmit={handleCreateTask} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Task Title
          </label>
          <Input
            type="text"
            value={newTask.title}
            onChange={handleTaskTitleChange}
            placeholder="Enter task title"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Initial Prompt (Optional)
          </label>
          <Textarea
            value={newTask.initial_message}
            onChange={handleInitialMessageChange}
            placeholder="Describe what you want to do with this task, including as much detail and context as possible. This will be used to start the conversation with the AI assistant."
            rows={6}
          />
        </div>

        {/* Project Selection - only when no projectId prop */}
        {!projectId && (
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Project
            </label>
            <select
              value={selectedProjectId}
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
        {selectedProjectId && (
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
                      to={`/projects/${selectedProjectId}?tab=settings`}
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
                  value={newTask.codebase_id ?? ''}
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

            {newTask.codebase_id && (
              <div className="col-span-1">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Base Branch
                </label>
                <Input
                  type="text"
                  value={newTask.base_branch}
                  onChange={handleBaseBranchChange}
                  placeholder="origin/main"
                />
              </div>
            )}
          </div>
        )}

        {/* Working Branch Configuration */}
        {newTask.codebase_id && (
          <div>
            <div className="flex items-center mb-2">
              <input
                type="checkbox"
                id="auto-generate-branch"
                checked={autoGenerateBranch}
                onChange={handleAutoGenerateChange}
                className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="auto-generate-branch" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Auto-generate working branch
              </label>
            </div>
            {!autoGenerateBranch && (
              <Input
                type="text"
                value={newTask.working_branch}
                onChange={handleWorkingBranchChange}
                placeholder="custom-branch-name"
              />
            )}
          </div>
        )}

        {/* Custom Fields */}
        <CustomFieldInputs
          definitions={customFieldDefinitions}
          values={customFieldValues}
          onChange={handleCustomFieldChange}
          loading={customFieldsLoading}
        />

        <div className="flex justify-end space-x-3 pt-4">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isCreating}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={isCreating}
            disabled={!newTask.title.trim() || !newTask.codebase_id || !selectedProjectId || isCreating || !areMandatoryFieldsFilled()}
          >
            Create Task
          </Button>
        </div>
      </form>
    </Modal>
  )
}
