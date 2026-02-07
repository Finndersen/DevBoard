import { useState, useCallback, useEffect } from 'react'
import { Modal, Button, Input, Textarea } from '../ui'
import { useCreateCodebase } from '../../hooks/useCodebases'
import type { Codebase, MergeMethod, BranchHandling } from '../../lib/api'

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
    default_branch: '',
    merge_method: '',
    branch_handling: '',
    setup_command: '',
    max_worktrees: '' as string  // Empty string = null (unlimited)
  })

  const [error, setError] = useState<string | null>(null)

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setNewCodebase({
        name: '',
        description: '',
        local_path: '',
        default_branch: '',
        merge_method: '',
        branch_handling: '',
        setup_command: '',
        max_worktrees: ''
      })
      setError(null)
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

  const handleDefaultBranchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, default_branch: e.target.value }))
  }, [])

  const handleMergeMethodChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setNewCodebase(prev => ({ ...prev, merge_method: e.target.value }))
  }, [])

  const handleBranchHandlingChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setNewCodebase(prev => ({ ...prev, branch_handling: e.target.value }))
  }, [])

  const handleSetupCommandChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, setup_command: e.target.value }))
  }, [])

  const handleMaxWorktreesChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, max_worktrees: e.target.value }))
  }, [])

  const handleCreateCodebase = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      // Convert max_worktrees from string to number or null
      const maxWorktreesValue = newCodebase.max_worktrees === ''
        ? null
        : parseInt(newCodebase.max_worktrees, 10)

      const createdCodebase = await createCodebase({
        name: newCodebase.name,
        description: newCodebase.description,
        local_path: newCodebase.local_path,
        default_branch: newCodebase.default_branch || null,
        merge_method: (newCodebase.merge_method || null) as MergeMethod | null,
        branch_handling: (newCodebase.branch_handling || null) as BranchHandling | null,
        setup_command: newCodebase.setup_command || null,
        max_worktrees: maxWorktreesValue
      })

      // Reset form
      setNewCodebase({
        name: '',
        description: '',
        local_path: '',
        default_branch: '',
        merge_method: '',
        branch_handling: '',
        setup_command: '',
        max_worktrees: ''
      })
      setError(null)

      onClose()

      // Call success callback if provided
      if (onSuccess && createdCodebase) {
        onSuccess(createdCodebase)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create codebase'
      setError(errorMessage)
      console.error('Failed to create codebase:', err)
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
            Default Branch
          </label>
          <Input
            type="text"
            value={newCodebase.default_branch}
            onChange={handleDefaultBranchChange}
            placeholder="Leave empty to auto-detect"
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Auto-detected from remote HEAD reference, or falls back to 'main'/'master' branch
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Merge Method
          </label>
          <select
            value={newCodebase.merge_method}
            onChange={handleMergeMethodChange}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Squash (default)</option>
            <option value="squash">Squash</option>
            <option value="rebase">Rebase</option>
            <option value="merge_commit">Merge Commit</option>
          </select>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Method used when merging task branches into the default branch
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Branch Handling
          </label>
          <select
            value={newCodebase.branch_handling}
            onChange={handleBranchHandlingChange}
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          >
            <option value="">Auto-detect</option>
            <option value="local_merge">Local Merge</option>
            <option value="github_pr">GitHub PR</option>
            <option value="manual">Manual</option>
          </select>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            How task branches are merged. Auto-detect uses GitHub PR if a remote URL exists, otherwise Local Merge
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Setup Command
          </label>
          <Input
            type="text"
            value={newCodebase.setup_command}
            onChange={handleSetupCommandChange}
            placeholder="e.g., npm install or pip install -e ."
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Shell command to run after setting up a new worktree (e.g., install dependencies)
          </p>
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

        {error && (
          <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 p-3 rounded-md">
            {error}
          </div>
        )}

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
