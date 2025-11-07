import { useEffect, useCallback, memo } from 'react'
import { FolderIcon, LinkIcon, PencilIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import type { Codebase } from '../lib/api'
import { useCodebase, useUpdateCodebase, useEditableField } from '../hooks'
import { useTabTitle } from '../hooks/useTabTitle'
import { useDataStore } from '../stores/dataStore'
import { Card, Input, Textarea, ErrorMessage, Button } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'

interface CodebaseDetailProps {
  id: string
}

function CodebaseDetail({ id }: CodebaseDetailProps) {
  const { data: codebase, loading, error, refetch } = useCodebase(id)
  const { setCodebase } = useDataStore()

  // Fetch codebase when id changes (supports both initial mount and tab switching)
  useEffect(() => {
    refetch()
  }, [id, refetch])

  // Store codebase in DataStore when loaded
  useEffect(() => {
    if (codebase) {
      setCodebase(codebase)
    }
  }, [codebase, setCodebase])

  // Update tab title when codebase data is loaded
  useTabTitle('codebase', id)

  // Memoize save functions to prevent infinite re-creation
  const { mutate: updateCodebase } = useUpdateCodebase()

  const saveNameField = useCallback(
    (value: string) => updateCodebase({ id: id!, codebase: { name: value } }),
    [updateCodebase, id]
  )

  const saveDescriptionField = useCallback(
    (value: string) => updateCodebase({ id: id!, codebase: { description: value } }),
    [updateCodebase, id]
  )

  const saveLocalPathField = useCallback(
    (value: string) => updateCodebase({ id: id!, codebase: { local_path: value } }),
    [updateCodebase, id]
  )

  const saveRepositoryUrlField = useCallback(
    (value: string) =>
      updateCodebase({ id: id!, codebase: { repository_url: value || null } }),
    [updateCodebase, id]
  )

  // Use editable field hooks
  const nameField = useEditableField(codebase?.name || '', saveNameField)
  const descriptionField = useEditableField(codebase?.description || '', saveDescriptionField)
  const localPathField = useEditableField(codebase?.local_path || '', saveLocalPathField)
  const repositoryUrlField = useEditableField(
    codebase?.repository_url || '',
    saveRepositoryUrlField
  )

  // Loading state
  if (loading && !codebase) {
    return (
      <div className={layouts.centerContainer}>
        <div className={loadingSpinner.container}>
          <div className={loadingSpinner.spinner}></div>
          <p className={textColors.muted}>Loading codebase...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className={layouts.centerContainer}>
        <ErrorMessage message="Failed to load codebase" />
      </div>
    )
  }

  // Not found state
  if (!codebase) {
    return (
      <div className={layouts.centerContainer}>
        <ErrorMessage message="Codebase not found" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Codebase Details</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          View and manage codebase information
        </p>
      </div>

      {/* Codebase Information */}
      <Card>
        <div className="space-y-6">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Name
            </label>
            {nameField.isEditing ? (
              <div className="flex items-center gap-2">
                <Input
                  value={nameField.editedValue}
                  onChange={(e) => nameField.setEditedValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') nameField.save()
                    if (e.key === 'Escape') nameField.cancelEditing()
                  }}
                  placeholder="Enter codebase name"
                  autoFocus
                />
                <Button
                  onClick={nameField.save}
                  variant="secondary"
                  size="sm"
                  className="p-1.5 min-w-[28px] h-9 border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                  title="Save (Enter)"
                  loading={nameField.saving}
                >
                  <CheckIcon className="w-4 h-4" />
                </Button>
                <Button
                  onClick={nameField.cancelEditing}
                  variant="secondary"
                  size="sm"
                  className="p-1.5 min-w-[28px] h-9 border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                  title="Cancel (Escape)"
                >
                  <XMarkIcon className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group">
                <span className="text-gray-900 dark:text-white">{codebase.name}</span>
                <Button
                  onClick={nameField.startEditing}
                  variant="ghost"
                  size="sm"
                  className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Edit name"
                >
                  <PencilIcon className="w-4 h-4" />
                </Button>
              </div>
            )}
            {nameField.error && <ErrorMessage message={nameField.error} />}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Description
            </label>
            {descriptionField.isEditing ? (
              <div className="space-y-2">
                <Textarea
                  value={descriptionField.editedValue}
                  onChange={(e) => descriptionField.setEditedValue(e.target.value)}
                  placeholder="Enter codebase description"
                  rows={3}
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={descriptionField.save}
                    variant="secondary"
                    size="sm"
                    className="border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                    loading={descriptionField.saving}
                  >
                    <CheckIcon className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={descriptionField.cancelEditing}
                    variant="secondary"
                    size="sm"
                    className="border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                  >
                    <XMarkIcon className="w-4 h-4 mr-1" />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="group">
                <div className="flex items-start gap-2">
                  <p className="text-gray-900 dark:text-white flex-1 whitespace-pre-wrap">
                    {codebase.description || (
                      <span className="text-gray-400 italic">No description</span>
                    )}
                  </p>
                  <Button
                    onClick={descriptionField.startEditing}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit description"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {descriptionField.error && <ErrorMessage message={descriptionField.error} />}
          </div>

          {/* Local Path */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <FolderIcon className="h-4 w-4" />
              Local Path
            </label>
            {localPathField.isEditing ? (
              <div className="space-y-2">
                <Input
                  value={localPathField.editedValue}
                  onChange={(e) => localPathField.setEditedValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') localPathField.save()
                    if (e.key === 'Escape') localPathField.cancelEditing()
                  }}
                  placeholder="Enter local file system path"
                  className="font-mono text-sm"
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={localPathField.save}
                    variant="secondary"
                    size="sm"
                    className="border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                    loading={localPathField.saving}
                  >
                    <CheckIcon className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={localPathField.cancelEditing}
                    variant="secondary"
                    size="sm"
                    className="border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                  >
                    <XMarkIcon className="w-4 h-4 mr-1" />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="group">
                <div className="flex items-center gap-2">
                  <code className="text-sm text-gray-900 dark:text-white bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1">
                    {codebase.local_path}
                  </code>
                  <Button
                    onClick={localPathField.startEditing}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit local path"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {localPathField.error && <ErrorMessage message={localPathField.error} />}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Absolute path to the codebase on your local file system
            </p>
          </div>

          {/* Repository URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <LinkIcon className="h-4 w-4" />
              Repository URL
            </label>
            {repositoryUrlField.isEditing ? (
              <div className="space-y-2">
                <Input
                  value={repositoryUrlField.editedValue}
                  onChange={(e) => repositoryUrlField.setEditedValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') repositoryUrlField.save()
                    if (e.key === 'Escape') repositoryUrlField.cancelEditing()
                  }}
                  placeholder="https://github.com/username/repo (optional)"
                  type="url"
                  className="font-mono text-sm"
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={repositoryUrlField.save}
                    variant="secondary"
                    size="sm"
                    className="border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                    loading={repositoryUrlField.saving}
                  >
                    <CheckIcon className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={repositoryUrlField.cancelEditing}
                    variant="secondary"
                    size="sm"
                    className="border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                  >
                    <XMarkIcon className="w-4 h-4 mr-1" />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="group">
                <div className="flex items-center gap-2">
                  {codebase.repository_url ? (
                    <a
                      href={codebase.repository_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 dark:text-blue-400 hover:underline font-mono bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1"
                    >
                      {codebase.repository_url}
                    </a>
                  ) : (
                    <span className="text-sm text-gray-400 italic flex-1">
                      No repository URL
                    </span>
                  )}
                  <Button
                    onClick={repositoryUrlField.startEditing}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit repository URL"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {repositoryUrlField.error && <ErrorMessage message={repositoryUrlField.error} />}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Optional Git repository URL
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default memo(CodebaseDetail)
