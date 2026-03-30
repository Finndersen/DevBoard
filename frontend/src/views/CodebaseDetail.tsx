import { useEffect, useCallback, memo, useRef, useState } from 'react'
import { FolderIcon, LinkIcon, PencilIcon, CheckIcon, XMarkIcon, CodeBracketIcon, ArrowPathIcon, Square3Stack3DIcon, CommandLineIcon } from '@heroicons/react/24/outline'
import type { Codebase, MergeMethod, BranchHandling } from '../lib/api'
import { useCodebase, useUpdateCodebase, useEditableField } from '../hooks'
import { useViewTitle } from '../hooks/useViewTitle'
import { useDataStore } from '../stores/dataStore'
import { Card, Input, Textarea, ErrorMessage, Button } from '../components/ui'
import { loadingSpinner, layouts, textColors, borderColors, surfaces } from '../styles/designSystem'
import InViewTabs from '../components/common/InViewTabs'
import WorktreeSlotsTab from '../components/codebase/WorktreeSlotsTab'

// Merge method options - how commits are combined during merge
const MERGE_METHOD_OPTIONS: { value: MergeMethod; label: string; description: string }[] = [
  { value: 'squash', label: 'Squash', description: 'Squash commits into a single commit' },
  { value: 'rebase', label: 'Rebase', description: 'Rebase for linear history' },
  { value: 'merge_commit', label: 'Merge Commit', description: 'Standard merge with merge commit' },
]

// Branch handling options - where/how the feature branch is finalized
const BRANCH_HANDLING_OPTIONS: { value: BranchHandling; label: string; description: string }[] = [
  { value: 'local_merge', label: 'Local Merge', description: 'Merge branch locally' },
  { value: 'github_pr', label: 'GitHub PR', description: 'Create PR for review, merge via GitHub' },
  { value: 'manual', label: 'Manual', description: 'No automatic handling - manage branch manually' },
]

const CODEBASE_TABS = [
  { id: 'details', label: 'Details' },
  { id: 'worktrees', label: 'Worktrees' },
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
  useViewTitle('codebase', id)

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

  const saveSetupCommandField = useCallback(
    (value: string) =>
      updateCodebase({ id: id!, codebase: { setup_command: value || null } }),
    [updateCodebase, id]
  )

  const saveDeveloperContextField = useCallback(
    (value: string) =>
      updateCodebase({ id: id!, codebase: { developer_context: value || null } }),
    [updateCodebase, id]
  )

  // Merge method state
  const [mergeMethodEditing, setMergeMethodEditing] = useState(false)
  const [mergeMethodSaving, setMergeMethodSaving] = useState(false)
  const [mergeMethodError, setMergeMethodError] = useState<string | null>(null)

  // Branch handling state
  const [branchHandlingEditing, setBranchHandlingEditing] = useState(false)
  const [branchHandlingSaving, setBranchHandlingSaving] = useState(false)
  const [branchHandlingError, setBranchHandlingError] = useState<string | null>(null)

  // Max worktrees state
  const [maxWorktreesEditing, setMaxWorktreesEditing] = useState(false)
  const [maxWorktreesSaving, setMaxWorktreesSaving] = useState(false)
  const [maxWorktreesError, setMaxWorktreesError] = useState<string | null>(null)
  const [maxWorktreesValue, setMaxWorktreesValue] = useState<string>('')

  // Tab state
  const [activeTab, setActiveTab] = useState<string>('details')

  // Initialize max worktrees value when codebase loads
  useEffect(() => {
    if (codebase) {
      setMaxWorktreesValue(codebase.max_worktrees === null ? '' : String(codebase.max_worktrees))
    }
  }, [codebase?.max_worktrees])

  const getMaxWorktreesDisplayValue = (value: number | null): string => {
    if (value === null) return 'Unlimited (default)'
    if (value === 0) return 'Main repository only'
    return `Maximum ${value} worktree${value === 1 ? '' : 's'}`
  }

  const saveMaxWorktrees = useCallback(
    async (value: string) => {
      setMaxWorktreesSaving(true)
      setMaxWorktreesError(null)
      try {
        // Convert string to number or null
        const numValue = value === '' ? null : parseInt(value, 10)
        if (value !== '' && (isNaN(numValue!) || numValue! < 0)) {
          setMaxWorktreesError('Please enter a valid non-negative number or leave empty')
          setMaxWorktreesSaving(false)
          return
        }
        await updateCodebase({ id: id!, codebase: { max_worktrees: numValue } })
        setMaxWorktreesEditing(false)
      } catch (err) {
        setMaxWorktreesError(err instanceof Error ? err.message : 'Failed to save')
      } finally {
        setMaxWorktreesSaving(false)
      }
    },
    [updateCodebase, id]
  )

  const saveMergeMethod = useCallback(
    async (value: MergeMethod) => {
      setMergeMethodSaving(true)
      setMergeMethodError(null)
      try {
        await updateCodebase({ id: id!, codebase: { merge_method: value } })
        setMergeMethodEditing(false)
      } catch (err) {
        setMergeMethodError(err instanceof Error ? err.message : 'Failed to save')
      } finally {
        setMergeMethodSaving(false)
      }
    },
    [updateCodebase, id]
  )

  const saveBranchHandling = useCallback(
    async (value: BranchHandling) => {
      setBranchHandlingSaving(true)
      setBranchHandlingError(null)
      try {
        await updateCodebase({ id: id!, codebase: { branch_handling: value } })
        setBranchHandlingEditing(false)
      } catch (err) {
        setBranchHandlingError(err instanceof Error ? err.message : 'Failed to save')
      } finally {
        setBranchHandlingSaving(false)
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
  const setupCommandField = useEditableField(
    codebase?.setup_command || '',
    saveSetupCommandField
  )
  const developerContextField = useEditableField(
    codebase?.developer_context || '',
    saveDeveloperContextField
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
    <div className="max-w-4xl mx-auto flex flex-col h-full gap-6">
      {/* Header */}
      <div className="space-y-2 shrink-0">
        <h1 className={`text-2xl font-bold ${textColors.primary}`}>Codebase Details</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          View and manage codebase information
        </p>
      </div>

      {/* Tab Navigation */}
      <InViewTabs
        tabs={CODEBASE_TABS}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Tab Content - scrollable area */}
      <div className="flex-1 overflow-auto min-h-0">

      {/* Details Tab Content */}
      {activeTab === 'details' && (
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
                <span className={textColors.primary}>{codebase.name}</span>
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
                  <p className={`${textColors.primary} flex-1 whitespace-pre-wrap`}>
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
                  <code className={`text-sm ${textColors.primary} bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1`}>
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
                  <code className={`text-sm ${textColors.primary} bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1`}>
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

          {/* Branch Handling */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <ArrowPathIcon className="h-4 w-4" />
              Branch Handling
            </label>
            {branchHandlingEditing ? (
              <div className="space-y-2">
                <select
                  value={codebase.branch_handling}
                  onChange={(e) => saveBranchHandling(e.target.value as BranchHandling)}
                  disabled={branchHandlingSaving}
                  className={`w-full px-3 py-2 text-sm border ${borderColors.input} rounded-md ${surfaces.raised} ${textColors.primary} focus:ring-2 focus:ring-blue-500 focus:border-blue-500`}
                >
                  {BRANCH_HANDLING_OPTIONS.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                      disabled={option.value === 'github_pr' && !codebase.repository_url}
                    >
                      {option.label} - {option.description}
                      {option.value === 'github_pr' && !codebase.repository_url ? ' (requires repository URL)' : ''}
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => setBranchHandlingEditing(false)}
                    variant="secondary"
                    size="sm"
                    className="border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                    disabled={branchHandlingSaving}
                  >
                    <XMarkIcon className="w-4 h-4 mr-1" />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="group">
                <div className="flex items-center gap-2">
                  <span className={`text-sm ${textColors.primary} bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1`}>
                    {BRANCH_HANDLING_OPTIONS.find((o) => o.value === codebase.branch_handling)?.label || codebase.branch_handling}
                    <span className="text-gray-500 dark:text-gray-400 ml-2">
                      ({BRANCH_HANDLING_OPTIONS.find((o) => o.value === codebase.branch_handling)?.description})
                    </span>
                  </span>
                  <Button
                    onClick={() => setBranchHandlingEditing(true)}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit branch handling"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {branchHandlingError && <ErrorMessage message={branchHandlingError} />}
            {codebase.branch_handling === 'github_pr' && !codebase.repository_url && (
              <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                GitHub PR handling requires a repository URL to be configured
              </p>
            )}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Where and how the feature branch is finalized when completing tasks
            </p>
          </div>

          {/* Merge Method */}
          {codebase.branch_handling !== 'manual' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                <ArrowPathIcon className="h-4 w-4" />
                Merge Method
              </label>
              {mergeMethodEditing ? (
                <div className="space-y-2">
                  <select
                    value={codebase.merge_method}
                    onChange={(e) => saveMergeMethod(e.target.value as MergeMethod)}
                    disabled={mergeMethodSaving}
                    className={`w-full px-3 py-2 text-sm border ${borderColors.input} rounded-md ${surfaces.raised} ${textColors.primary} focus:ring-2 focus:ring-blue-500 focus:border-blue-500`}
                  >
                    {MERGE_METHOD_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label} - {option.description}
                      </option>
                    ))}
                  </select>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => setMergeMethodEditing(false)}
                      variant="secondary"
                      size="sm"
                      className="border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                      disabled={mergeMethodSaving}
                    >
                      <XMarkIcon className="w-4 h-4 mr-1" />
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="group">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm ${textColors.primary} bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1`}>
                      {MERGE_METHOD_OPTIONS.find((o) => o.value === codebase.merge_method)?.label || codebase.merge_method}
                      <span className="text-gray-500 dark:text-gray-400 ml-2">
                        ({MERGE_METHOD_OPTIONS.find((o) => o.value === codebase.merge_method)?.description})
                      </span>
                    </span>
                    <Button
                      onClick={() => setMergeMethodEditing(true)}
                      variant="ghost"
                      size="sm"
                      className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Edit merge method"
                    >
                      <PencilIcon className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
              {mergeMethodError && <ErrorMessage message={mergeMethodError} />}
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                How commits are combined when merging the feature branch
              </p>
            </div>
          )}

          {/* Max Worktrees */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <Square3Stack3DIcon className="h-4 w-4" />
              Max Worktrees
            </label>
            {maxWorktreesEditing ? (
              <div className="space-y-2">
                <Input
                  type="number"
                  min="0"
                  value={maxWorktreesValue}
                  onChange={(e) => setMaxWorktreesValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveMaxWorktrees(maxWorktreesValue)
                    if (e.key === 'Escape') {
                      setMaxWorktreesEditing(false)
                      setMaxWorktreesError(null)
                    }
                  }}
                  placeholder="Leave empty for unlimited"
                  className="font-mono text-sm"
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => saveMaxWorktrees(maxWorktreesValue)}
                    variant="secondary"
                    size="sm"
                    className="border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                    loading={maxWorktreesSaving}
                  >
                    <CheckIcon className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={() => {
                      setMaxWorktreesEditing(false)
                      setMaxWorktreesError(null)
                    }}
                    variant="secondary"
                    size="sm"
                    className="border border-gray-300 bg-gray-50 text-gray-600 hover:bg-gray-100 hover:border-gray-400"
                    disabled={maxWorktreesSaving}
                  >
                    <XMarkIcon className="w-4 h-4 mr-1" />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="group">
                <div className="flex items-center gap-2">
                  <span className={`text-sm ${textColors.primary} bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1`}>
                    {codebase.max_worktrees === null ? (
                      <>
                        <span className="font-medium">Unlimited</span>
                        <span className="text-gray-500 dark:text-gray-400 ml-2">(default)</span>
                      </>
                    ) : codebase.max_worktrees === 0 ? (
                      <>
                        <span className="font-medium">0</span>
                        <span className="text-gray-500 dark:text-gray-400 ml-2">(use main repository only)</span>
                      </>
                    ) : (
                      <>
                        <span className="font-medium">{codebase.max_worktrees}</span>
                        <span className="text-gray-500 dark:text-gray-400 ml-2">(maximum worktree directories)</span>
                      </>
                    )}
                  </span>
                  <Button
                    onClick={() => {
                      setMaxWorktreesValue(codebase.max_worktrees?.toString() ?? '')
                      setMaxWorktreesEditing(true)
                    }}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit max worktrees"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {maxWorktreesError && <ErrorMessage message={maxWorktreesError} />}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Controls worktree slot allocation: empty = unlimited, 0 = main repo only, N = max N worktrees
            </p>
          </div>

          {/* Setup Command */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <CommandLineIcon className="h-4 w-4" />
              Setup Command
            </label>
            {setupCommandField.isEditing ? (
              <div className="space-y-2">
                <Textarea
                  value={setupCommandField.editedValue}
                  onChange={(e) => setupCommandField.setEditedValue(e.target.value)}
                  placeholder="e.g., npm install, pip install -e ., ./scripts/setup.sh"
                  rows={3}
                  className="font-mono text-sm"
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={setupCommandField.save}
                    variant="secondary"
                    size="sm"
                    className="border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                    loading={setupCommandField.saving}
                  >
                    <CheckIcon className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={setupCommandField.cancelEditing}
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
                  {codebase.setup_command ? (
                    <code className={`text-sm ${textColors.primary} bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1 whitespace-pre-wrap font-mono`}>
                      {codebase.setup_command}
                    </code>
                  ) : (
                    <span className="text-sm text-gray-400 italic flex-1">
                      No setup command configured
                    </span>
                  )}
                  <Button
                    onClick={setupCommandField.startEditing}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit setup command"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {setupCommandField.error && <ErrorMessage message={setupCommandField.error} />}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Shell command to run when a workspace is allocated (e.g., install dependencies). Should be fast and idempotent.
            </p>
          </div>

          {/* Developer Context */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
              <CommandLineIcon className="h-4 w-4" />
              Developer Context
            </label>
            {developerContextField.isEditing ? (
              <div className="space-y-2">
                <Textarea
                  value={developerContextField.editedValue}
                  onChange={(e) => developerContextField.setEditedValue(e.target.value)}
                  placeholder="e.g., Fast checks: ruff check . --fix && ruff format . && pyright&#10;Tests: pytest"
                  rows={5}
                  className="font-mono text-sm"
                  autoFocus
                />
                <div className="flex items-center gap-2">
                  <Button
                    onClick={developerContextField.save}
                    variant="secondary"
                    size="sm"
                    className="border border-green-300 bg-green-50 text-green-700 hover:bg-green-100 hover:border-green-400"
                    loading={developerContextField.saving}
                  >
                    <CheckIcon className="w-4 h-4 mr-1" />
                    Save
                  </Button>
                  <Button
                    onClick={developerContextField.cancelEditing}
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
                  {codebase.developer_context ? (
                    <pre className={`text-sm ${textColors.primary} bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded flex-1 whitespace-pre-wrap font-mono`}>
                      {codebase.developer_context}
                    </pre>
                  ) : (
                    <span className="text-sm text-gray-400 italic flex-1">
                      No developer context configured
                    </span>
                  )}
                  <Button
                    onClick={developerContextField.startEditing}
                    variant="ghost"
                    size="sm"
                    className="p-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit developer context"
                  >
                    <PencilIcon className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
            {developerContextField.error && <ErrorMessage message={developerContextField.error} />}
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Persistent context about this codebase available to all AI agents — testing commands, linting setup, conventions, etc.
            </p>
          </div>
        </div>
      </Card>
      )}

      {/* Worktrees Tab Content */}
      {activeTab === 'worktrees' && (
        <WorktreeSlotsTab codebaseId={id} />
      )}

      </div>
    </div>
  )
}

export default memo(CodebaseDetail)
