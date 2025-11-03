import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal, Button, Input, Textarea } from '../ui'
import { apiClient } from '../../lib/api'
import { useCodebases } from '../../hooks'

interface CreateTaskModalProps {
  isOpen: boolean
  onClose: () => void
  projectId: string
}

export default function CreateTaskModal({ isOpen, onClose, projectId }: CreateTaskModalProps) {
  const navigate = useNavigate()
  const { data: codebases } = useCodebases()

  const [newTask, setNewTask] = useState({
    title: '',
    codebase_id: null as number | null,
    remote_task_id: null as string | null,
    specification_content: ''
  })
  const [isCreating, setIsCreating] = useState(false)

  // Individual change handlers to avoid object spread on every keystroke
  const handleTaskTitleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewTask(prev => ({ ...prev, title: e.target.value }))
  }, [])

  const handleTaskCodebaseChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setNewTask(prev => ({ ...prev, codebase_id: e.target.value ? Number(e.target.value) : null }))
  }, [])

  const handleTaskSpecificationChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewTask(prev => ({ ...prev, specification_content: e.target.value }))
  }, [])

  const handleCreateTask = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setIsCreating(true)
    try {
      const taskData = {
        title: newTask.title,
        codebase_id: newTask.codebase_id,
        remote_task_id: newTask.remote_task_id,
        specification_content: newTask.specification_content
      }
      const createdTask = await apiClient.createTask(projectId, taskData)

      // Reset form
      setNewTask({
        title: '',
        codebase_id: null,
        remote_task_id: null,
        specification_content: ''
      })

      onClose()
      // Navigate to the newly created task
      navigate(`/tasks/${createdTask.id}`)
    } catch (error) {
      console.error('Failed to create task:', error)
    } finally {
      setIsCreating(false)
    }
  }, [newTask, projectId, navigate, onClose])

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
            Codebase (Optional)
          </label>
          <select
            value={newTask.codebase_id ?? ''}
            onChange={handleTaskCodebaseChange}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="">None</option>
            {codebases?.map((codebase) => (
              <option key={codebase.id} value={codebase.id}>
                {codebase.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Task Specification (Optional)
          </label>
          <Textarea
            value={newTask.specification_content}
            onChange={handleTaskSpecificationChange}
            placeholder="Describe what needs to be done..."
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
            disabled={!newTask.title.trim() || isCreating}
          >
            Create Task
          </Button>
        </div>
      </form>
    </Modal>
  )
}
