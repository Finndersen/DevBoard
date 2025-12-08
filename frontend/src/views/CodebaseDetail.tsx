import { useEffect, useCallback, memo, useRef, useState } from 'react'
import { FolderIcon, LinkIcon, PencilIcon, CheckIcon, XMarkIcon, CodeBracketIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import type { Codebase, MergeStrategy } from '../lib/api'
import { useCodebase, useUpdateCodebase, useEditableField } from '../hooks'
import { useTabTitle } from '../hooks/useTabTitle'
import { useDataStore } from '../stores/dataStore'
import { Card, Input, Textarea, ErrorMessage, Button } from '../components/ui'
import { loadingSpinner, layouts, textColors } from '../styles/designSystem'

// Merge strategy display labels
const MERGE_STRATEGY_OPTIONS: { value: MergeStrategy; label: string; description: string }[] = [
  { value: 'github_pr', label: 'GitHub PR', description: 'Create a GitHub PR for review and merge' },
  { value: 'squash', label: 'Squash', description: 'Squash commits into a single commit' },
  { value: 'rebase', label: 'Rebase', description: 'Rebase for linear history' },
  { value: 'merge_commit', label: 'Merge Commit', description: 'Standard merge with merge commit' },
  { value: 'none', label: 'Manual', description: 'No automatic git operations' },
]

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

  // Use ref to store refetch function to avoid dependency issues
  const refetchRef = useRef(refetch)
  refetchRef.current = refetch

  // Memoize the updateCache function to refetch after updates
  const updateCache = useCallback(() => {
    refetchRef.current()
  }, [])

  // Memoize save functions to prevent infinite re-creation
  const { mutate: updateCodebase } = useUpdateCodebase({ updateCache })

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

  const saveDefaultBranchField = useCallback(
    (value: string) => updateCodebase({ id: id!, codebase: { default_branch: value } }),
    [updateCodebase, id]
  )

  // Merge strategy state
  const [mergeStrategyEditing, setMergeStrategyEditing] = useState(false)
  const [mergeStrategySaving, setMergeStrategySaving] = useState(false)
  const [mergeStrategyError, setMergeStrategyError] = useState<string | null>(null)

  const saveMergeStrategy = useCallback(
    async (value: MergeStrategy) => {
      setMergeStrategySaving(true)
      setMergeStrategyError(null)
      try {
        await updateCodebase({ id: id!, codebase: { merge_strategy: value } })
        setMergeStrategyEditing(false)
      } catch (err) {
        setMergeStrategyError(err instanceof Error ? err.message : 'Failed to save')
      } finally {
        setMergeStrategySaving(false)
      }
    },
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
  const defaultBranchField = useEditableField(
    codebase?.default_branch || '',
    saveDefaultBranchField
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

          {/* Default Branch */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <CodeBracketIcon className="h-4 w-4" />
              Default Branch
            </label>
            {defaultBranchField.isEditing ? (
              <div className="space-y-2">
                <Input
                  value={defaultBranchField.editedValue}
                  onChange={(e) => defaultBranchField.setEditedValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') defaultBranchField.save()
                    if (e.key === 'Escape') defaultBranchField.cancelEditing()
                  }}
                  placeholder="e.g., origin/main"
                  className="font-mono text-sm"
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={defaultBranchField.save}
                    variant="secondary"
                    size="sm"
                    className="border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                    loading={defaultBranchField.saving}
                  >
                    <CheckIcon className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={defaultBranchField.cancelEditing}
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
                    {codebase.default_branch}
                  </code>
                  <Button
                    onClick={defaultBranchField.startEditing}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit default branch"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {defaultBranchField.error && <ErrorMessage message={defaultBranchField.error} />}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Default base branch for new tasks (e.g., origin/main)
            </p>
          </div>

          {/* Merge Strategy */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <ArrowPathIcon className="h-4 w-4" />
              Merge Strategy
            </label>
            {mergeStrategyEditing ? (
              <div className="space-y-2">
                <select
                  value={codebase.merge_strategy}
                  onChange={(e) => saveMergeStrategy(e.target.value as MergeStrategy)}
                  disabled={mergeStrategySaving}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {MERGE_STRATEGY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} - {option.description}
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => setMergeStrategyEditing(false)}
                    variant="secondary"
                    size="sm"
                    className="border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                    disabled={mergeStrategySaving}
                  >
                    <XMarkIcon className="w-4 h-4 mr-1" />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="group">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-900 dark:text-white bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1">
                    {MERGE_STRATEGY_OPTIONS.find((o) => o.value === codebase.merge_strategy)?.label || codebase.merge_strategy}
                    <span className="text-gray-500 dark:text-gray-400 ml-2">
                      ({MERGE_STRATEGY_OPTIONS.find((o) => o.value === codebase.merge_strategy)?.description})
                    </span>
                  </span>
                  <Button
                    onClick={() => setMergeStrategyEditing(true)}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit merge strategy"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {mergeStrategyError && <ErrorMessage message={mergeStrategyError} />}
            {codebase.merge_strategy === 'github_pr' && !codebase.repository_url && (
              <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                ⚠️ GitHub PR strategy requires a repository URL to be configured
              </p>
            )}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              How feature branches are merged when completing tasks
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}

export default memo(CodebaseDetail)
