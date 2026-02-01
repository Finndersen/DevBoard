import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import CodebaseBootstrapWizard from '../CodebaseBootstrapWizard'
import { apiClient } from '../../../lib/api'

// Mock the API client
vi.mock('../../../lib/api', () => ({
  apiClient: {
    validateCodebasePath: vi.fn(),
    previewBootstrap: vi.fn(),
    bootstrapCodebase: vi.fn(),
    createCodebase: vi.fn(),
    listDirectory: vi.fn(),
  },
}))

describe('CodebaseBootstrapWizard', () => {
  const mockOnClose = vi.fn()
  const mockOnSuccess = vi.fn()

  const defaultProps = {
    isOpen: true,
    onClose: mockOnClose,
    onSuccess: mockOnSuccess,
  }

  const mockValidationResult = {
    exists: true,
    is_directory: true,
    has_git: false,
    has_commits: false,
    has_remote: false,
    remote_url: null,
    current_branch: null,
    needs_bootstrap: true,
    detected_project_type: 'python',
  }

  const mockPreviewResult = {
    files: [
      { path: '.gitignore', content: '# Python gitignore content', file_type: 'gitignore' },
      { path: 'README.md', content: '# Test Project\n\nDescription', file_type: 'readme' },
      { path: 'CLAUDE.md', content: '# Test Project\n\nAI instructions', file_type: 'claude_md' },
    ],
  }

  const mockBootstrapResult = {
    success: true,
    commit_hash: 'abc123def',
    files_created: ['.gitignore', 'README.md', 'CLAUDE.md'],
    error_message: null,
  }

  const mockCodebase = {
    id: 1,
    name: 'Test Project',
    description: 'Test description',
    repository_url: null,
    local_path: '/test/path',
    default_branch: 'main',
    merge_method: 'squash' as const,
    branch_handling: 'local_merge' as const,
    max_worktrees: null,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.validateCodebasePath).mockResolvedValue(mockValidationResult)
    vi.mocked(apiClient.previewBootstrap).mockResolvedValue(mockPreviewResult)
    vi.mocked(apiClient.bootstrapCodebase).mockResolvedValue(mockBootstrapResult)
    vi.mocked(apiClient.createCodebase).mockResolvedValue(mockCodebase)
    vi.mocked(apiClient.listDirectory).mockResolvedValue({
      current_path: '/home/user',
      parent_path: '/home',
      directories: ['Documents', 'Projects'],
    })
  })

  it('renders when open', () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    expect(screen.getByText('Bootstrap New Codebase')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    render(<CodebaseBootstrapWizard {...defaultProps} isOpen={false} />)

    expect(screen.queryByText('Bootstrap New Codebase')).not.toBeInTheDocument()
  })

  it('shows wizard steps', () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    expect(screen.getByText('Path')).toBeInTheDocument()
    expect(screen.getByText('Basic Info')).toBeInTheDocument()
    expect(screen.getByText('Files')).toBeInTheDocument()
    expect(screen.getByText('Git Config')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
  })

  it('starts at step 1 (Path)', () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    expect(screen.getByText('Directory Path')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('/path/to/your/project')).toBeInTheDocument()
  })

  it('shows cancel button on first step', () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })

  it('calls onClose when cancel is clicked', () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('validates path when user leaves input field', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.blur(pathInput)

    await waitFor(() => {
      expect(apiClient.validateCodebasePath).toHaveBeenCalledWith('/test/path')
    })
  })

  it('shows validation status after path validation', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.blur(pathInput)

    await waitFor(() => {
      expect(screen.getByText('Directory Status')).toBeInTheDocument()
    })
  })

  it('shows detected project type', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.blur(pathInput)

    await waitFor(() => {
      expect(screen.getByText('Detected: python')).toBeInTheDocument()
    })
  })

  it('navigates to step 2 when Next is clicked with valid path', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(screen.getByText('Project Name')).toBeInTheDocument()
    })
  })

  it('shows Back button on step 2', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument()
    })
  })

  it('auto-populates name from path', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/home/user/my-project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      const nameInput = screen.getByPlaceholderText('my-awesome-project')
      expect(nameInput).toHaveValue('my-project')
    })
  })

  it('navigates through all steps to review', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Step 1: Path
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    // Step 2: Basic Info
    await waitFor(() => {
      expect(screen.getByText('Project Name')).toBeInTheDocument()
    })
    const nameInput = screen.getByPlaceholderText('my-awesome-project')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    // Step 3: Files
    await waitFor(() => {
      expect(screen.getByText('.gitignore')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    // Step 4: Git Config
    await waitFor(() => {
      expect(screen.getByText('Default Branch Name')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    // Step 5: Review
    await waitFor(() => {
      expect(screen.getByText('Review Configuration')).toBeInTheDocument()
    })
  })

  it('shows file checkboxes on files step', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Navigate to files step
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(screen.getByText('Project Name')).toBeInTheDocument()
    })

    const nameInput = screen.getByPlaceholderText('my-awesome-project')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(screen.getByText('.gitignore')).toBeInTheDocument()
      expect(screen.getByText('README.md')).toBeInTheDocument()
      expect(screen.getByText('CLAUDE.md')).toBeInTheDocument()
    })
  })

  it('shows git config inputs on git step', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Navigate to git config step
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Project Name')).toBeInTheDocument())
    const nameInput = screen.getByPlaceholderText('my-awesome-project')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('.gitignore')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(screen.getByText('Default Branch Name')).toBeInTheDocument()
      expect(screen.getByText('Initial Commit Message')).toBeInTheDocument()
      expect(screen.getByText('Remote URL (Optional)')).toBeInTheDocument()
    })
  })

  it('shows review summary on final step', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Navigate through all steps
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Project Name')).toBeInTheDocument())
    const nameInput = screen.getByPlaceholderText('my-awesome-project')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })
    const descInput = screen.getByPlaceholderText('A brief description of your project')
    fireEvent.change(descInput, { target: { value: 'Test description' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('.gitignore')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Default Branch Name')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    // Check review content
    await waitFor(() => {
      expect(screen.getByText('Review Configuration')).toBeInTheDocument()
      expect(screen.getByText('Test Project')).toBeInTheDocument()
      expect(screen.getByText('Test description')).toBeInTheDocument()
      expect(screen.getByText(/\.gitignore.*README\.md.*CLAUDE\.md/)).toBeInTheDocument()
    })
  })

  it('shows Bootstrap & Add Codebase button on final step', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Navigate to final step
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Project Name')).toBeInTheDocument())
    const nameInput = screen.getByPlaceholderText('my-awesome-project')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('.gitignore')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Default Branch Name')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Bootstrap & Add Codebase' })).toBeInTheDocument()
    })
  })

  it('executes bootstrap and creates codebase on submit', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Navigate to final step
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Project Name')).toBeInTheDocument())
    const nameInput = screen.getByPlaceholderText('my-awesome-project')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('.gitignore')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Default Branch Name')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Bootstrap & Add Codebase' })).toBeInTheDocument())

    // Execute bootstrap
    fireEvent.click(screen.getByRole('button', { name: 'Bootstrap & Add Codebase' }))

    await waitFor(() => {
      expect(apiClient.bootstrapCodebase).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/test/path',
          name: 'Test Project',
          branch_name: 'main',
        })
      )
    })

    await waitFor(() => {
      expect(apiClient.createCodebase).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled()
      expect(mockOnSuccess).toHaveBeenCalledWith(mockCodebase)
    })
  })

  it('shows error message when bootstrap fails', async () => {
    vi.mocked(apiClient.bootstrapCodebase).mockResolvedValue({
      success: false,
      commit_hash: null,
      files_created: [],
      error_message: 'Bootstrap failed: permission denied',
    })

    render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Navigate to final step and submit
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Project Name')).toBeInTheDocument())
    const nameInput = screen.getByPlaceholderText('my-awesome-project')
    fireEvent.change(nameInput, { target: { value: 'Test Project' } })
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('.gitignore')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByText('Default Branch Name')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Bootstrap & Add Codebase' })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Bootstrap & Add Codebase' }))

    // Should not create codebase or call success
    await waitFor(() => {
      expect(apiClient.bootstrapCodebase).toHaveBeenCalled()
    })

    expect(apiClient.createCodebase).not.toHaveBeenCalled()
    expect(mockOnSuccess).not.toHaveBeenCalled()
  })

  it('uses initialPath when provided', async () => {
    render(<CodebaseBootstrapWizard {...defaultProps} initialPath="/initial/path" />)

    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    expect(pathInput).toHaveValue('/initial/path')
  })

  it('resets form when modal reopens', async () => {
    const { rerender } = render(<CodebaseBootstrapWizard {...defaultProps} />)

    // Fill in some data
    const pathInput = screen.getByPlaceholderText('/path/to/your/project')
    fireEvent.change(pathInput, { target: { value: '/test/path' } })

    // Close modal
    rerender(<CodebaseBootstrapWizard {...defaultProps} isOpen={false} />)

    // Reopen modal
    rerender(<CodebaseBootstrapWizard {...defaultProps} isOpen={true} />)

    // Form should be reset
    const newPathInput = screen.getByPlaceholderText('/path/to/your/project')
    expect(newPathInput).toHaveValue('')
  })
})
