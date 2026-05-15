import { useState, useCallback, useEffect } from 'react'
import { Modal, Button, Input, Textarea } from '../ui'
import Alert from '../ui/Alert'
import InViewTabs from '../common/InViewTabs'
import { useCreateCodebase, useCloneCodebase, useInitCodebase } from '../../hooks/useCodebases'
import type { Codebase, MergeMethod, BranchHandling } from '../../lib/api'

type Mode = 'existing' | 'clone' | 'new'

const TABS = [
  { id: 'existing', label: 'Existing Path' },
  { id: 'clone', label: 'Clone Repo' },
  { id: 'new', label: 'New Repo' },
]

const SUBMIT_LABELS: Record<Mode, string> = {
  existing: 'Add Codebase',
  clone: 'Clone & Create',
  new: 'Initialize & Create',
}

interface AdvancedFields {
  default_branch: string
  merge_method: string
  branch_handling: string
  setup_command: string
  max_worktrees: string
}

interface ExistingFields {
  name: string
  description: string
  local_path: string
}

interface CloneFields {
  repository_url: string
  parent_directory: string
  name: string
  description: string
  nameManuallyEdited: boolean
}

interface NewFields {
  name: string
  directory: string
  description: string
}

const EMPTY_ADVANCED: AdvancedFields = {
  default_branch: '',
  merge_method: '',
  branch_handling: '',
  setup_command: '',
  max_worktrees: '',
}

const EMPTY_EXISTING: ExistingFields = {
  name: '',
  description: '',
  local_path: '',
}

const EMPTY_CLONE: CloneFields = {
  repository_url: '',
  parent_directory: '',
  name: '',
  description: '',
  nameManuallyEdited: false,
}

const EMPTY_NEW: NewFields = {
  name: '',
  directory: '',
  description: '',
}

function deriveNameFromUrl(url: string): string {
  const trimmed = url.replace(/\/$/, '').replace(/\.git$/, '')
  const parts = trimmed.split('/')
  return parts[parts.length - 1] ?? ''
}

function parseMaxWorktrees(value: string): number | null {
  if (value === '') return null
  const parsed = parseInt(value, 10)
  return Number.isNaN(parsed) ? null : parsed
}

interface CreateCodebaseModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (codebase: Codebase) => void
}

const LABEL_CLASS = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2'
const SELECT_CLASS =
  'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-white/[0.06] text-gray-900 dark:text-gray-100'
const HINT_CLASS = 'mt-1 text-xs text-gray-500 dark:text-gray-400'

export default function CreateCodebaseModal({ isOpen, onClose, onSuccess }: CreateCodebaseModalProps) {
  const { mutate: createCodebase, loading: isCreatingExisting } = useCreateCodebase()
  const { mutate: cloneCodebase, loading: isCloning } = useCloneCodebase()
  const { mutate: initCodebase, loading: isIniting } = useInitCodebase()

  const [mode, setMode] = useState<Mode>('existing')
  const [existingFields, setExistingFields] = useState<ExistingFields>(EMPTY_EXISTING)
  const [cloneFields, setCloneFields] = useState<CloneFields>(EMPTY_CLONE)
  const [newFields, setNewFields] = useState<NewFields>(EMPTY_NEW)
  const [advanced, setAdvanced] = useState<AdvancedFields>(EMPTY_ADVANCED)
  const [error, setError] = useState<string | null>(null)

  const isLoading = isCreatingExisting || isCloning || isIniting

  const resetAll = useCallback(() => {
    setMode('existing')
    setExistingFields(EMPTY_EXISTING)
    setCloneFields(EMPTY_CLONE)
    setNewFields(EMPTY_NEW)
    setAdvanced(EMPTY_ADVANCED)
    setError(null)
  }, [])

  useEffect(() => {
    if (!isOpen) {
      resetAll()
    }
  }, [isOpen, resetAll])

  const handleModeChange = useCallback((id: string) => {
    setMode(id as Mode)
    setExistingFields(EMPTY_EXISTING)
    setCloneFields(EMPTY_CLONE)
    setNewFields(EMPTY_NEW)
    setAdvanced(EMPTY_ADVANCED)
    setError(null)
  }, [])

  // Clone URL auto-derive name
  const handleCloneUrlChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const url = e.target.value
    setCloneFields(prev => ({
      ...prev,
      repository_url: url,
      name: prev.nameManuallyEdited ? prev.name : deriveNameFromUrl(url),
    }))
  }, [])

  const handleCloneNameChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setCloneFields(prev => ({ ...prev, name: e.target.value, nameManuallyEdited: true }))
  }, [])

  const handleAdvancedChange = useCallback(
    (field: keyof AdvancedFields) =>
      (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        setAdvanced(prev => ({ ...prev, [field]: e.target.value }))
      },
    []
  )

  const buildCommonOptional = useCallback(
    () => ({
      default_branch: advanced.default_branch || null,
      merge_method: (advanced.merge_method || null) as MergeMethod | null,
      branch_handling: (advanced.branch_handling || null) as BranchHandling | null,
      setup_command: advanced.setup_command || null,
      max_worktrees: parseMaxWorktrees(advanced.max_worktrees),
    }),
    [advanced]
  )

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      setError(null)

      try {
        let created: Codebase | undefined

        if (mode === 'existing') {
          created = await createCodebase({
            name: existingFields.name,
            description: existingFields.description,
            local_path: existingFields.local_path,
            ...buildCommonOptional(),
          })
        } else if (mode === 'clone') {
          created = await cloneCodebase({
            repository_url: cloneFields.repository_url,
            parent_directory: cloneFields.parent_directory,
            name: cloneFields.name || null,
            description: cloneFields.description || null,
            ...buildCommonOptional(),
          })
        } else {
          created = await initCodebase({
            name: newFields.name,
            directory: newFields.directory,
            description: newFields.description || null,
            ...buildCommonOptional(),
          })
        }

        resetAll()
        onClose()

        if (onSuccess && created) {
          onSuccess(created)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create codebase')
      }
    },
    [mode, existingFields, cloneFields, newFields, buildCommonOptional, createCodebase, cloneCodebase, initCodebase, onClose, onSuccess, resetAll]
  )

  const isSubmitDisabled = (() => {
    if (isLoading) return true
    if (mode === 'existing') return !existingFields.name.trim() || !existingFields.local_path.trim()
    if (mode === 'clone') return !cloneFields.repository_url.trim() || !cloneFields.parent_directory.trim()
    return !newFields.name.trim() || !newFields.directory.trim()
  })()

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add New Codebase">
      <div className="space-y-4">
        <InViewTabs tabs={TABS} activeTab={mode} onTabChange={handleModeChange} />

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'existing' && (
            <>
              <div>
                <label className={LABEL_CLASS}>Name</label>
                <Input
                  type="text"
                  value={existingFields.name}
                  onChange={e => setExistingFields(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter codebase name"
                  required
                  autoFocus
                />
              </div>
              <div>
                <label className={LABEL_CLASS}>Description</label>
                <Textarea
                  value={existingFields.description}
                  onChange={e => setExistingFields(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of the codebase"
                  rows={3}
                />
              </div>
              <div>
                <label className={LABEL_CLASS}>Local Path</label>
                <Input
                  type="text"
                  value={existingFields.local_path}
                  onChange={e => setExistingFields(prev => ({ ...prev, local_path: e.target.value }))}
                  placeholder="/path/to/your/codebase"
                  required
                />
              </div>
            </>
          )}

          {mode === 'clone' && (
            <>
              <div>
                <label className={LABEL_CLASS}>Repository URL</label>
                <Input
                  type="text"
                  value={cloneFields.repository_url}
                  onChange={handleCloneUrlChange}
                  placeholder="https://github.com/org/repo.git"
                  required
                  autoFocus
                />
              </div>
              <div>
                <label className={LABEL_CLASS}>Parent Directory</label>
                <Input
                  type="text"
                  value={cloneFields.parent_directory}
                  onChange={e => setCloneFields(prev => ({ ...prev, parent_directory: e.target.value }))}
                  placeholder="/path/to/parent"
                  required
                />
              </div>
              <div>
                <label className={LABEL_CLASS}>Name</label>
                <Input
                  type="text"
                  value={cloneFields.name}
                  onChange={handleCloneNameChange}
                  placeholder="Auto-derived from URL"
                />
                <p className={HINT_CLASS}>Auto-derived from the repository URL, editable</p>
              </div>
              <div>
                <label className={LABEL_CLASS}>Description</label>
                <Textarea
                  value={cloneFields.description}
                  onChange={e => setCloneFields(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of the codebase"
                  rows={3}
                />
              </div>
            </>
          )}

          {mode === 'new' && (
            <>
              <div>
                <label className={LABEL_CLASS}>Name</label>
                <Input
                  type="text"
                  value={newFields.name}
                  onChange={e => setNewFields(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter project name"
                  required
                  autoFocus
                />
              </div>
              <div>
                <label className={LABEL_CLASS}>Directory</label>
                <Input
                  type="text"
                  value={newFields.directory}
                  onChange={e => setNewFields(prev => ({ ...prev, directory: e.target.value }))}
                  placeholder="/path/to/new-repo"
                  required
                />
                <p className={HINT_CLASS}>Full path where the new repository will be initialized</p>
              </div>
              <div>
                <label className={LABEL_CLASS}>Description</label>
                <Textarea
                  value={newFields.description}
                  onChange={e => setNewFields(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of the project"
                  rows={3}
                />
              </div>
            </>
          )}

          <details>
            <summary className="cursor-pointer text-sm font-medium text-gray-600 dark:text-gray-400 select-none">
              Advanced Settings
            </summary>
            <div className="mt-3 space-y-4">
              <div>
                <label className={LABEL_CLASS}>Default Branch</label>
                <Input
                  type="text"
                  value={advanced.default_branch}
                  onChange={handleAdvancedChange('default_branch')}
                  placeholder="Leave empty to auto-detect"
                />
                <p className={HINT_CLASS}>
                  Auto-detected from remote HEAD reference, or falls back to 'main'/'master' branch
                </p>
              </div>
              <div>
                <label className={LABEL_CLASS}>Merge Method</label>
                <select
                  value={advanced.merge_method}
                  onChange={handleAdvancedChange('merge_method')}
                  className={SELECT_CLASS}
                >
                  <option value="">Squash (default)</option>
                  <option value="squash">Squash</option>
                  <option value="rebase">Rebase</option>
                  <option value="merge_commit">Merge Commit</option>
                </select>
                <p className={HINT_CLASS}>
                  Method used when merging task branches into the default branch
                </p>
              </div>
              <div>
                <label className={LABEL_CLASS}>Branch Handling</label>
                <select
                  value={advanced.branch_handling}
                  onChange={handleAdvancedChange('branch_handling')}
                  className={SELECT_CLASS}
                >
                  <option value="">Auto-detect</option>
                  <option value="direct_merge">Direct Merge</option>
                  <option value="github_pr">GitHub PR</option>
                  <option value="manual">Manual</option>
                </select>
                <p className={HINT_CLASS}>
                  How task branches are merged. Auto-detect uses GitHub PR if a remote URL exists, otherwise Local Merge
                </p>
              </div>
              <div>
                <label className={LABEL_CLASS}>Setup Command</label>
                <Input
                  type="text"
                  value={advanced.setup_command}
                  onChange={handleAdvancedChange('setup_command')}
                  placeholder="e.g., npm install or pip install -e ."
                />
                <p className={HINT_CLASS}>
                  Shell command to run after setting up a new worktree (e.g., install dependencies)
                </p>
              </div>
              <div>
                <label className={LABEL_CLASS}>Max Worktrees</label>
                <Input
                  type="number"
                  min="0"
                  value={advanced.max_worktrees}
                  onChange={handleAdvancedChange('max_worktrees')}
                  placeholder="Leave empty for unlimited"
                />
                <p className={HINT_CLASS}>
                  Empty = unlimited, 0 = main repo only, N = max N worktrees
                </p>
              </div>
            </div>
          </details>

          {error && <Alert variant="error">{error}</Alert>}

          <div className="flex justify-end space-x-3 pt-4">
            <Button type="button" variant="secondary" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={isLoading}
              disabled={isSubmitDisabled}
            >
              {SUBMIT_LABELS[mode]}
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  )
}
