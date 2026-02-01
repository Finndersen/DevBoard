import { useState, useCallback, useEffect } from 'react'
import { FolderOpenIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { Modal, Button, Input, Textarea } from '../ui'
import { useCreateCodebase, useCodebaseBootstrap } from '../../hooks'
import DirectoryBrowserModal from './DirectoryBrowserModal'
import CodebaseBootstrapWizard from './CodebaseBootstrapWizard'
import type { Codebase } from '../../lib/api'

interface CreateCodebaseModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (codebase: Codebase) => void
}

export default function CreateCodebaseModal({ isOpen, onClose, onSuccess }: CreateCodebaseModalProps) {
  const { mutate: createCodebase, loading: isCreating } = useCreateCodebase()
  const {
    validation,
    validationLoading,
    validationError,
    validatePath,
    clearValidation,
    reset: resetBootstrap,
  } = useCodebaseBootstrap()

  const [newCodebase, setNewCodebase] = useState({
    name: '',
    description: '',
    local_path: '',
    max_worktrees: '' as string  // Empty string = null (unlimited)
  })
  const [isBrowserOpen, setIsBrowserOpen] = useState(false)
  const [isWizardOpen, setIsWizardOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setNewCodebase({
        name: '',
        description: '',
        local_path: '',
        max_worktrees: ''
      })
      setCreateError(null)
      clearValidation()
      resetBootstrap()
    }
  }, [isOpen, clearValidation, resetBootstrap])

  const handleNameChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, name: e.target.value }))
  }, [])

  const handleDescriptionChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewCodebase(prev => ({ ...prev, description: e.target.value }))
  }, [])

  const handleLocalPathChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, local_path: e.target.value }))
    setCreateError(null)
    clearValidation()
  }, [clearValidation])

  // Validate path when it changes (debounced via blur)
  const handlePathBlur = useCallback(async () => {
    if (newCodebase.local_path.trim()) {
      await validatePath(newCodebase.local_path)
    }
  }, [newCodebase.local_path, validatePath])

  const handleBrowseClick = useCallback(() => {
    setIsBrowserOpen(true)
  }, [])

  const handleDirectorySelect = useCallback(async (path: string) => {
    setNewCodebase(prev => ({ ...prev, local_path: path }))
    setCreateError(null)
    // Validate the selected path
    if (path.trim()) {
      await validatePath(path)
    }
  }, [validatePath])

  const handleMaxWorktreesChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setNewCodebase(prev => ({ ...prev, max_worktrees: e.target.value }))
  }, [])

  const handleOpenWizard = useCallback(() => {
    setIsWizardOpen(true)
  }, [])

  const handleWizardClose = useCallback(() => {
    setIsWizardOpen(false)
  }, [])

  const handleWizardSuccess = useCallback((codebase: Codebase) => {
    setIsWizardOpen(false)
    onClose()
    if (onSuccess) {
      onSuccess(codebase)
    }
  }, [onClose, onSuccess])

  const handleCreateCodebase = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError(null)

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
      const message = error instanceof Error ? error.message : 'Failed to create codebase'
      setCreateError(message)
    }
  }, [newCodebase, createCodebase, onClose, onSuccess])

  // Check if bootstrap is needed
  const needsBootstrap = validation?.needs_bootstrap === true

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
          <div className="flex gap-2">
            <Input
              type="text"
              value={newCodebase.local_path}
              onChange={handleLocalPathChange}
              onBlur={handlePathBlur}
              placeholder="/path/to/your/codebase"
              required
            />
            <Button
              type="button"
              variant="secondary"
              onClick={handleBrowseClick}
              className="shrink-0"
            >
              <FolderOpenIcon className="w-5 h-5" />
            </Button>
          </div>

          {/* Validation loading indicator */}
          {validationLoading && (
            <div className="mt-2 flex items-center gap-2 text-gray-500 dark:text-gray-400">
              <div className="animate-spin h-4 w-4 border-2 border-gray-500 border-t-transparent rounded-full" />
              <span className="text-sm">Validating path...</span>
            </div>
          )}

          {/* Validation error */}
          {validationError && (
            <p className="mt-2 text-sm text-red-500">{validationError}</p>
          )}

          {/* Bootstrap needed warning */}
          {needsBootstrap && !validationLoading && (
            <div className="mt-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
              <div className="flex items-start gap-2">
                <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200 font-medium">
                    This directory needs to be bootstrapped
                  </p>
                  <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
                    {!validation?.has_git
                      ? 'Git is not initialized in this directory.'
                      : 'This repository has no commits yet.'}
                    {' '}Use the Bootstrap Wizard to initialize git and create starter files.
                  </p>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={handleOpenWizard}
                    className="mt-2"
                  >
                    Open Bootstrap Wizard
                  </Button>
                </div>
              </div>
            </div>
          )}
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

        {/* Create error message */}
        {createError && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
            <p className="text-sm text-red-700 dark:text-red-300">{createError}</p>
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
            disabled={
              !newCodebase.name.trim() ||
              !newCodebase.local_path.trim() ||
              isCreating ||
              needsBootstrap ||
              validationLoading
            }
          >
            Add Codebase
          </Button>
        </div>
      </form>

      <DirectoryBrowserModal
        isOpen={isBrowserOpen}
        onClose={() => setIsBrowserOpen(false)}
        onSelect={handleDirectorySelect}
        initialPath={newCodebase.local_path || undefined}
      />

      <CodebaseBootstrapWizard
        isOpen={isWizardOpen}
        onClose={handleWizardClose}
        onSuccess={handleWizardSuccess}
        initialPath={newCodebase.local_path}
      />
    </Modal>
  )
}
