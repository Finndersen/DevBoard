import { useState, useCallback, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal, Button, Input, Textarea } from '../ui'
import { apiClient } from '../../lib/api'
import { useCodebases } from '../../hooks'
import { useDataStore } from '../../stores/dataStore'

interface CreateTaskModalProps {
  isOpen: boolean
  onClose: () => void
  projectId: string
}

export default function CreateTaskModal({ isOpen, onClose, projectId }: CreateTaskModalProps) {
  const navigate = useNavigate()
  const { data: codebases } = useCodebases()
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

  // Get selected codebase for default_branch lookup
  const selectedCodebase = useMemo(() => {
    if (!newTask.codebase_id || !codebases) return null
    return codebases.find(c => c.id === newTask.codebase_id) ?? null
  }, [newTask.codebase_id, codebases])

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
        state: initialMessage ? { initialMessage } : undefined
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
      maxWidth="lg"
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
            Codebase
          </label>
          <select
            value={newTask.codebase_id ?? ''}
            onChange={handleTaskCodebaseChange}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            required
          >
            <option value="">Select a codebase</option>
            {codebases?.map((codebase) => (
              <option key={codebase.id} value={codebase.id}>
                {codebase.name}
              </option>
            ))}
          </select>
        </div>

        {/* Working Branch Configuration */}
        {newTask.codebase_id && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Working Branch (Optional)
              </label>
              <Input
                type="text"
                value={newTask.working_branch}
                onChange={handleWorkingBranchChange}
                placeholder="Leave empty to auto-generate"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Branch name is auto-generated from task title if not specified
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Base Branch
              </label>
              <Input
                type="text"
                value={newTask.base_branch}
                onChange={handleBaseBranchChange}
                placeholder="e.g., origin/main"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                The branch to create the working branch from (auto-populated from codebase default)
              </p>
            </div>
          </>
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
            disabled={!newTask.title.trim() || !newTask.codebase_id || isCreating}
          >
            Create Task
          </Button>
        </div>
      </form>
    </Modal>
  )
}
