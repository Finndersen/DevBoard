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
    local_path: ''
  })

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setNewCodebase({
        name: '',
        description: '',
        local_path: ''
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

  const handleCreateCodebase = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const createdCodebase = await createCodebase(newCodebase)

      // Reset form
      setNewCodebase({
        name: '',
        description: '',
        local_path: ''
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
