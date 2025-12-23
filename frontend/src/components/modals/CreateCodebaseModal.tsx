import { useState, useCallback, useEffect } from 'react'
import { Modal, Button, Input, Textarea } from '../ui'
import { useCreateCodebase } from '../../hooks/useCodebases'
import type { Codebase } from '../../lib/api'

interface CreateCodebaseModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (codebase: Codebase) => void
}

export default function CreateCodebaseModal({ isOpen, onClose, onSuccess }: CreateCodebaseModalProps) {
  const { mutate: createCodebase, loading: isCreating } = useCreateCodebase()

  const [newCodebase, setNewCodebase] = useState({
    name: '',
    description: '',
    local_path: '',
    max_worktrees: '' as string  // Empty string = null (unlimited)
  })

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setNewCodebase({
        name: '',
        description: '',
        local_path: '',
        max_worktrees: ''
      })
    }
  }, [isOpen])

  const handleNameChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, name: e.target.value }))
  }, [])

  const handleDescriptionChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewCodebase(prev => ({ ...prev, description: e.target.value }))
  }, [])

  const handleLocalPathChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, local_path: e.target.value }))
  }, [])

  const handleMaxWorktreesChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, max_worktrees: e.target.value }))
  }, [])

  const handleCreateCodebase = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      // Convert max_worktrees from string to number or null
      const maxWorktreesValue = newCodebase.max_worktrees === ''
        ? null
        : parseInt(newCodebase.max_worktrees, 10)

      const createdCodebase = await createCodebase({
        name: newCodebase.name,
        description: newCodebase.description,
        local_path: newCodebase.local_path,
        max_worktrees: maxWorktreesValue
      })

      // Reset form
      setNewCodebase({
        name: '',
        description: '',
        local_path: '',
        max_worktrees: ''
      })

      onClose()

      // Call success callback if provided
      if (onSuccess && createdCodebase) {
        onSuccess(createdCodebase)
      }
    } catch (error) {
      console.error('Failed to create codebase:', error)
    }
  }, [newCodebase, createCodebase, onClose, onSuccess])

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Add New Codebase"
    >
      <form onSubmit={handleCreateCodebase} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Name
          </label>
          <Input
            type="text"
            value={newCodebase.name}
            onChange={handleNameChange}
            placeholder="Enter codebase name"
            required
            autoFocus
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Description
          </label>
          <Textarea
            value={newCodebase.description}
            onChange={handleDescriptionChange}
            placeholder="Brief description of the codebase"
            rows={3}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Local Path
          </label>
          <Input
            type="text"
            value={newCodebase.local_path}
            onChange={handleLocalPathChange}
            placeholder="/path/to/your/codebase"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Max Worktrees
          </label>
          <Input
            type="number"
            min="0"
            value={newCodebase.max_worktrees}
            onChange={handleMaxWorktreesChange}
            placeholder="Leave empty for unlimited"
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Empty = unlimited, 0 = main repo only, N = max N worktrees
          </p>
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
            disabled={!newCodebase.name.trim() || !newCodebase.local_path.trim() || isCreating}
          >
            Add Codebase
          </Button>
        </div>
      </form>
    </Modal>
  )
}
