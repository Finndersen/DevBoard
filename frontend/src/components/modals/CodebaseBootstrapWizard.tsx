import { useState, useCallback, useEffect, useMemo } from 'react'
import {
  FolderOpenIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import { Modal, Button, Input, Textarea } from '../ui'
import WizardStepper from '../ui/WizardStepper'
import type { WizardStep } from '../ui/WizardStepper'
import { useCodebaseBootstrap } from '../../hooks/useCodebaseBootstrap'
import DirectoryBrowserModal from './DirectoryBrowserModal'
import type { BootstrapCodebaseRequest, Codebase } from '../../lib/api'
import { useCreateCodebase } from '../../hooks/useCodebases'

interface CodebaseBootstrapWizardProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (codebase: Codebase) => void
  initialPath?: string
}

const WIZARD_STEPS: WizardStep[] = [
  { id: 'path', label: 'Path' },
  { id: 'info', label: 'Basic Info' },
  { id: 'files', label: 'Files' },
  { id: 'git', label: 'Git Config' },
  { id: 'review', label: 'Review' },
]

interface FormState {
  path: string
  name: string
  description: string
  createGitignore: boolean
  createReadme: boolean
  createClaudeMd: boolean
  branchName: string
  initialCommitMessage: string
  remoteUrl: string
  pushToRemote: boolean
  maxWorktrees: string
}

export default function CodebaseBootstrapWizard({
  isOpen,
  onClose,
  onSuccess,
  initialPath = '',
}: CodebaseBootstrapWizardProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [isBrowserOpen, setIsBrowserOpen] = useState(false)
  const [form, setForm] = useState<FormState>({
    path: initialPath,
    name: '',
    description: '',
    createGitignore: true,
    createReadme: true,
    createClaudeMd: true,
    branchName: 'main',
    initialCommitMessage: 'Initial commit',
    remoteUrl: '',
    pushToRemote: false,
    maxWorktrees: '',
  })

  const {
    validation,
    validationLoading,
    validationError,
    validatePath,
    preview,
    previewLoading,
    loadPreview,
    bootstrapResult,
    bootstrapLoading,
    bootstrapError,
    executeBootstrap,
    reset: resetBootstrap,
  } = useCodebaseBootstrap()

  const { mutate: createCodebase, loading: isCreatingCodebase } = useCreateCodebase()

  // Reset wizard when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setCurrentStep(0)
      setForm({
        path: initialPath,
        name: '',
        description: '',
        createGitignore: true,
        createReadme: true,
        createClaudeMd: true,
        branchName: 'main',
        initialCommitMessage: 'Initial commit',
        remoteUrl: '',
        pushToRemote: false,
        maxWorktrees: '',
      })
      resetBootstrap()
    }
  }, [isOpen, initialPath, resetBootstrap])

  // Auto-populate name from path
  useEffect(() => {
    if (form.path && !form.name) {
      const pathParts = form.path.split('/').filter(Boolean)
      const suggestedName = pathParts[pathParts.length - 1] || ''
      if (suggestedName) {
        setForm(prev => ({ ...prev, name: suggestedName }))
      }
    }
  }, [form.path, form.name])

  // Load preview when reaching files step
  useEffect(() => {
    if (currentStep === 2 && form.path && form.name) {
      loadPreview(
        form.path,
        form.name,
        form.description,
        form.createGitignore,
        form.createReadme,
        form.createClaudeMd,
      )
    }
  }, [currentStep, form.path, form.name, form.description, form.createGitignore, form.createReadme, form.createClaudeMd, loadPreview])

  const handlePathValidate = useCallback(async () => {
    if (form.path) {
      await validatePath(form.path)
    }
  }, [form.path, validatePath])

  const handleDirectorySelect = useCallback((path: string) => {
    setForm(prev => ({ ...prev, path }))
  }, [])

  const handleInputChange = useCallback((field: keyof FormState, value: string | boolean) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }, [])

  const handleNext = useCallback(async () => {
    if (currentStep === 0) {
      // Validate path before proceeding
      const result = await validatePath(form.path)
      if (result && result.exists && result.is_directory) {
        setCurrentStep(prev => prev + 1)
      }
    } else if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(prev => prev + 1)
    }
  }, [currentStep, form.path, validatePath])

  const handleBack = useCallback(() => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1)
    }
  }, [currentStep])

  const handleExecuteBootstrap = useCallback(async () => {
    const request: BootstrapCodebaseRequest = {
      path: form.path,
      name: form.name,
      description: form.description,
      create_gitignore: form.createGitignore,
      create_readme: form.createReadme,
      create_claude_md: form.createClaudeMd,
      branch_name: form.branchName,
      initial_commit_message: form.initialCommitMessage,
      remote_url: form.remoteUrl || null,
      push_to_remote: form.pushToRemote,
    }

    const result = await executeBootstrap(request)
    if (result?.success) {
      // Now create the codebase
      try {
        const maxWorktreesValue = form.maxWorktrees === ''
          ? null
          : parseInt(form.maxWorktrees, 10)

        const createdCodebase = await createCodebase({
          name: form.name,
          description: form.description,
          local_path: form.path,
          default_branch: form.branchName,
          merge_method: 'squash',
          branch_handling: form.remoteUrl ? 'github_pr' : 'local_merge',
          max_worktrees: maxWorktreesValue,
        })

        onClose()
        if (onSuccess && createdCodebase) {
          onSuccess(createdCodebase)
        }
      } catch (error) {
        console.error('Failed to create codebase after bootstrap:', error)
      }
    }
  }, [form, executeBootstrap, createCodebase, onClose, onSuccess])

  // Determine if next button should be enabled
  const canProceed = useMemo(() => {
    switch (currentStep) {
      case 0: // Path step
        return form.path.trim() !== '' && !validationLoading
      case 1: // Basic info step
        return form.name.trim() !== ''
      case 2: // Files step
        return true
      case 3: // Git config step
        return form.branchName.trim() !== ''
      case 4: // Review step
        return true
      default:
        return false
    }
  }, [currentStep, form, validationLoading])

  const isLoading = bootstrapLoading || isCreatingCodebase

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return renderPathStep()
      case 1:
        return renderInfoStep()
      case 2:
        return renderFilesStep()
      case 3:
        return renderGitConfigStep()
      case 4:
        return renderReviewStep()
      default:
        return null
    }
  }

  const renderPathStep = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Directory Path
        </label>
        <div className="flex gap-2">
          <Input
            type="text"
            value={form.path}
            onChange={(e) => handleInputChange('path', e.target.value)}
            placeholder="/path/to/your/project"
            onBlur={handlePathValidate}
          />
          <Button
            type="button"
            variant="secondary"
            onClick={() => setIsBrowserOpen(true)}
            className="shrink-0"
          >
            <FolderOpenIcon className="w-5 h-5" />
          </Button>
        </div>
      </div>

      {validationLoading && (
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <div className="animate-spin h-4 w-4 border-2 border-gray-500 border-t-transparent rounded-full" />
          <span className="text-sm">Validating path...</span>
        </div>
      )}

      {validationError && (
        <div className="flex items-center gap-2 text-red-500">
          <ExclamationCircleIcon className="w-5 h-5" />
          <span className="text-sm">{validationError}</span>
        </div>
      )}

      {validation && !validationLoading && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-2">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white">Directory Status</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-2">
              {validation.exists ? (
                <CheckCircleIcon className="w-4 h-4 text-green-500" />
              ) : (
                <ExclamationCircleIcon className="w-4 h-4 text-yellow-500" />
              )}
              <span className="text-gray-600 dark:text-gray-400">
                {validation.exists ? 'Directory exists' : 'Will be created'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {validation.has_git ? (
                <CheckCircleIcon className="w-4 h-4 text-green-500" />
              ) : (
                <ExclamationCircleIcon className="w-4 h-4 text-yellow-500" />
              )}
              <span className="text-gray-600 dark:text-gray-400">
                {validation.has_git ? 'Git initialized' : 'Git will be initialized'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {validation.has_commits ? (
                <CheckCircleIcon className="w-4 h-4 text-green-500" />
              ) : (
                <ExclamationCircleIcon className="w-4 h-4 text-yellow-500" />
              )}
              <span className="text-gray-600 dark:text-gray-400">
                {validation.has_commits ? 'Has commits' : 'Initial commit will be created'}
              </span>
            </div>
            {validation.detected_project_type && (
              <div className="flex items-center gap-2">
                <DocumentTextIcon className="w-4 h-4 text-blue-500" />
                <span className="text-gray-600 dark:text-gray-400">
                  Detected: {validation.detected_project_type}
                </span>
              </div>
            )}
          </div>
          {!validation.is_directory && validation.exists && (
            <div className="mt-2 text-red-500 text-sm">
              Path is not a directory. Please select a valid directory.
            </div>
          )}
        </div>
      )}

      <DirectoryBrowserModal
        isOpen={isBrowserOpen}
        onClose={() => setIsBrowserOpen(false)}
        onSelect={handleDirectorySelect}
        initialPath={form.path || undefined}
      />
    </div>
  )

  const renderInfoStep = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Project Name
        </label>
        <Input
          type="text"
          value={form.name}
          onChange={(e) => handleInputChange('name', e.target.value)}
          placeholder="my-awesome-project"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Description
        </label>
        <Textarea
          value={form.description}
          onChange={(e) => handleInputChange('description', e.target.value)}
          placeholder="A brief description of your project"
          rows={3}
        />
      </div>

      {validation?.detected_project_type && (
        <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <span className="text-sm text-blue-700 dark:text-blue-300">
            Detected project type: <strong>{validation.detected_project_type}</strong>
          </span>
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Max Worktrees
        </label>
        <Input
          type="number"
          min="0"
          value={form.maxWorktrees}
          onChange={(e) => handleInputChange('maxWorktrees', e.target.value)}
          placeholder="Leave empty for unlimited"
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Empty = unlimited, 0 = main repo only, N = max N worktrees
        </p>
      </div>
    </div>
  )

  const renderFilesStep = () => (
    <div className="space-y-4">
      <p className="text-sm text-gray-600 dark:text-gray-400">
        Select which files to create. Existing files will not be overwritten.
      </p>

      <div className="space-y-3">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.createGitignore}
            onChange={(e) => handleInputChange('createGitignore', e.target.checked)}
            className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <div>
            <span className="block font-medium text-gray-900 dark:text-white">.gitignore</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Ignore common build artifacts, dependencies, and IDE files
              {validation?.detected_project_type && (
                <span className="ml-1">
                  (tailored for {validation.detected_project_type})
                </span>
              )}
            </span>
          </div>
        </label>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.createReadme}
            onChange={(e) => handleInputChange('createReadme', e.target.checked)}
            className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <div>
            <span className="block font-medium text-gray-900 dark:text-white">README.md</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Project documentation with basic structure
            </span>
          </div>
        </label>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.createClaudeMd}
            onChange={(e) => handleInputChange('createClaudeMd', e.target.checked)}
            className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <div>
            <span className="block font-medium text-gray-900 dark:text-white">CLAUDE.md</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              AI assistant instructions and project guidelines
            </span>
          </div>
        </label>
      </div>

      {previewLoading && (
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <div className="animate-spin h-4 w-4 border-2 border-gray-500 border-t-transparent rounded-full" />
          <span className="text-sm">Loading preview...</span>
        </div>
      )}

      {preview && preview.files.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
            Files to be created:
          </h4>
          <div className="space-y-2">
            {preview.files.map((file) => (
              <details key={file.path} className="group">
                <summary className="cursor-pointer flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-blue-600">
                  <DocumentTextIcon className="w-4 h-4" />
                  {file.path}
                </summary>
                <pre className="mt-2 p-3 bg-gray-50 dark:bg-gray-900 rounded text-xs overflow-auto max-h-48">
                  {file.content}
                </pre>
              </details>
            ))}
          </div>
        </div>
      )}
    </div>
  )

  const renderGitConfigStep = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Default Branch Name
        </label>
        <Input
          type="text"
          value={form.branchName}
          onChange={(e) => handleInputChange('branchName', e.target.value)}
          placeholder="main"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Initial Commit Message
        </label>
        <Input
          type="text"
          value={form.initialCommitMessage}
          onChange={(e) => handleInputChange('initialCommitMessage', e.target.value)}
          placeholder="Initial commit"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          Remote URL (Optional)
        </label>
        <Input
          type="text"
          value={form.remoteUrl}
          onChange={(e) => handleInputChange('remoteUrl', e.target.value)}
          placeholder="https://github.com/user/repo.git"
        />
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Configure origin remote for pushing code to GitHub, GitLab, etc.
        </p>
      </div>

      {form.remoteUrl && (
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.pushToRemote}
            onChange={(e) => handleInputChange('pushToRemote', e.target.checked)}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-700 dark:text-gray-300">
            Push to remote after initial commit
          </span>
        </label>
      )}
    </div>
  )

  const renderReviewStep = () => (
    <div className="space-y-4">
      <h4 className="text-sm font-medium text-gray-900 dark:text-white">Review Configuration</h4>

      <div className="rounded-lg border border-gray-200 dark:border-gray-700 divide-y divide-gray-200 dark:divide-gray-700">
        <div className="p-3">
          <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">Path</dt>
          <dd className="mt-1 text-sm text-gray-900 dark:text-white font-mono">{form.path}</dd>
        </div>
        <div className="p-3">
          <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">Name</dt>
          <dd className="mt-1 text-sm text-gray-900 dark:text-white">{form.name}</dd>
        </div>
        {form.description && (
          <div className="p-3">
            <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">Description</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white">{form.description}</dd>
          </div>
        )}
        <div className="p-3">
          <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">Files to Create</dt>
          <dd className="mt-1 text-sm text-gray-900 dark:text-white">
            {[
              form.createGitignore && '.gitignore',
              form.createReadme && 'README.md',
              form.createClaudeMd && 'CLAUDE.md',
            ].filter(Boolean).join(', ') || 'None'}
          </dd>
        </div>
        <div className="p-3">
          <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">Branch</dt>
          <dd className="mt-1 text-sm text-gray-900 dark:text-white">{form.branchName}</dd>
        </div>
        <div className="p-3">
          <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">Commit Message</dt>
          <dd className="mt-1 text-sm text-gray-900 dark:text-white">{form.initialCommitMessage}</dd>
        </div>
        {form.remoteUrl && (
          <div className="p-3">
            <dt className="text-xs font-medium text-gray-500 dark:text-gray-400">Remote</dt>
            <dd className="mt-1 text-sm text-gray-900 dark:text-white font-mono">{form.remoteUrl}</dd>
            {form.pushToRemote && (
              <dd className="mt-1 text-xs text-blue-600 dark:text-blue-400">Will push after commit</dd>
            )}
          </div>
        )}
      </div>

      {bootstrapError && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <p className="text-sm text-red-700 dark:text-red-300">{bootstrapError}</p>
        </div>
      )}

      {bootstrapResult?.success && (
        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <p className="text-sm text-green-700 dark:text-green-300">
            Bootstrap completed successfully!
            {bootstrapResult.commit_hash && (
              <span className="block font-mono text-xs mt-1">
                Commit: {bootstrapResult.commit_hash.slice(0, 8)}
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  )

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Bootstrap New Codebase"
      maxWidth="lg"
    >
      <WizardStepper
        steps={WIZARD_STEPS}
        currentStep={currentStep}
        onStepClick={setCurrentStep}
        allowClickBack={!isLoading}
      />

      <div className="min-h-[300px]">
        {renderStepContent()}
      </div>

      <div className="flex justify-between pt-6 border-t border-gray-200 dark:border-gray-700 mt-6">
        <Button
          type="button"
          variant="secondary"
          onClick={currentStep === 0 ? onClose : handleBack}
          disabled={isLoading}
        >
          {currentStep === 0 ? 'Cancel' : 'Back'}
        </Button>

        <Button
          type="button"
          variant="primary"
          onClick={currentStep === WIZARD_STEPS.length - 1 ? handleExecuteBootstrap : handleNext}
          disabled={!canProceed || isLoading}
          loading={isLoading || validationLoading}
        >
          {currentStep === WIZARD_STEPS.length - 1 ? 'Bootstrap & Add Codebase' : 'Next'}
        </Button>
      </div>
    </Modal>
  )
}
