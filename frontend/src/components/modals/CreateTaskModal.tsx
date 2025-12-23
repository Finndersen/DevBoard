import { useState, useCallback, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Modal, Button, Input, Textarea } from '../ui'
import { apiClient } from '../../lib/api'
import { useProjectCodebases } from '../../hooks'
import { useDataStore } from '../../stores/dataStore'

interface CreateTaskModalProps {
  isOpen: boolean
  onClose: () => void
  projectId: string
}

export default function CreateTaskModal({ isOpen, onClose, projectId }: CreateTaskModalProps) {
  const navigate = useNavigate()
  const { data: codebases, loading: codebasesLoading, refetch: refetchCodebases } = useProjectCodebases(projectId)
  const { setTask, fetchProjectTasks } = useDataStore()

  const [newTask, setNewTask] = useState({
    title: '',
    codebase_id: null as number | null,
    remote_task_id: null as string | null,
    working_branch: '',
    base_branch: '',
    initial_message: ''
  })
  const [isCreating, setIsCreating] = useState(false)
  const [autoGenerateBranch, setAutoGenerateBranch] = useState(true)

  // Refetch codebases when modal opens (in case new ones were linked)
  useEffect(() => {
    if (isOpen) {
      refetchCodebases()
    }
  }, [isOpen, refetchCodebases])

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setNewTask({
        title: '',
        codebase_id: null,
        remote_task_id: null,
        working_branch: '',
        base_branch: '',
        initial_message: ''
      })
      setIsCreating(false)
      setAutoGenerateBranch(true)
    }
  }, [isOpen])

  // Individual change handlers to avoid object spread on every keystroke
  const handleTaskTitleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewTask(prev => ({ ...prev, title: e.target.value }))
  }, [])

  const handleTaskCodebaseChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const codebaseId = e.target.value ? Number(e.target.value) : null
    // Auto-populate base_branch from selected codebase's default_branch
    const selectedCodebase = codebaseId && codebases
      ? codebases.find(c => c.id === codebaseId)
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

  const handleCreateTask = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setIsCreating(true)
    try {
      const taskData: any = {
        title: newTask.title,
        codebase_id: newTask.codebase_id,
        remote_task_id: newTask.remote_task_id,
        specification_content: null  // Always empty, initial message is sent via chat
      }

      // Add working branch if provided (otherwise auto-generated)
      if (newTask.working_branch.trim()) {
        taskData.branch_name = newTask.working_branch.trim()
      }

      // Add base branch if provided
      if (newTask.base_branch.trim()) {
        taskData.base_branch = newTask.base_branch.trim()
      }

      const createdTask = await apiClient.createTask(projectId, taskData)

      // Update cache with new task
      setTask(createdTask)
      await fetchProjectTasks(projectId)

      // Store initial message for navigation
      const initialMessage = newTask.initial_message.trim() || null

      // Reset form
      setNewTask({
        title: '',
        codebase_id: null,
        remote_task_id: null,
        working_branch: '',
        base_branch: '',
        initial_message: ''
      })

      onClose()
      // Navigate to the newly created task, passing initial message in state
      navigate(`/tasks/${createdTask.id}`, {
        state: initialMessage ? { initialMessage, taskId: createdTask.id } : undefined
      })
    } catch (error) {
      console.error('Failed to create task:', error)
    } finally {
      setIsCreating(false)
    }
  }, [newTask, projectId, navigate, onClose, setTask, fetchProjectTasks])

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

        {/* Codebase and Base Branch */}
        <div className="grid grid-cols-4 gap-4">
          <div className="col-span-3">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Codebase
              </label>
              {codebasesLoading ? (
                <div className="text-sm text-gray-500 dark:text-gray-400">Loading codebases...</div>
              ) : !codebases || codebases.length === 0 ? (
                <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md">
                  <p className="text-sm text-amber-800 dark:text-amber-200 mb-2">
                    No codebases are linked to this project.
                  </p>
                  <p className="text-sm text-amber-700 dark:text-amber-300">
                    Please{' '}
                    <Link
                      to={`/projects/${projectId}?tab=settings`}
                      onClick={onClose}
                      className="font-medium underline hover:text-amber-900 dark:hover:text-amber-100"
                    >
                      link a codebase in project settings
                    </Link>
                    {' '}before creating a task.
                  </p>
                </div>
              ) : (
                <select
                  value={newTask.codebase_id ?? ''}
                  onChange={handleTaskCodebaseChange}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
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

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Initial Description (Optional)
          </label>
          <Textarea
            value={newTask.initial_message}
            onChange={handleInitialMessageChange}
            placeholder="Describe what you want to do with this task, including as much detail and context as possible. This will be used to start the conversation with the AI assistant."
            rows={6}
          />
        </div>

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
            disabled={!newTask.title.trim() || !newTask.codebase_id || isCreating || !codebases || codebases.length === 0}
          >
            Create Task
          </Button>
        </div>
      </form>
    </Modal>
  )
}
