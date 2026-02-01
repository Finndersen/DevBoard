import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import DirectoryBrowserModal from '../DirectoryBrowserModal'
import { apiClient } from '../../../lib/api'

// Mock the API client
vi.mock('../../../lib/api', () => ({
  apiClient: {
    listDirectory: vi.fn(),
  },
}))

describe('DirectoryBrowserModal', () => {
  const mockOnClose = vi.fn()
  const mockOnSelect = vi.fn()

  const defaultProps = {
    isOpen: true,
    onClose: mockOnClose,
    onSelect: mockOnSelect,
  }

  const mockDirectoryResponse = {
    current_path: '/home/user',
    parent_path: '/home',
    directories: ['Documents', 'Downloads', 'Projects'],
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.listDirectory).mockResolvedValue(mockDirectoryResponse)
  })

  it('renders when open', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Select Directory')).toBeInTheDocument()
    })
  })

  it('does not render when closed', () => {
    render(<DirectoryBrowserModal {...defaultProps} isOpen={false} />)

    expect(screen.queryByText('Select Directory')).not.toBeInTheDocument()
  })

  it('loads directory listing on open', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(apiClient.listDirectory).toHaveBeenCalled()
    })
  })

  it('displays directories', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Documents')).toBeInTheDocument()
      expect(screen.getByText('Downloads')).toBeInTheDocument()
      expect(screen.getByText('Projects')).toBeInTheDocument()
    })
  })

  it('navigates to subdirectory on double click', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Documents')).toBeInTheDocument()
    })

    // Mock the response for the subdirectory
    vi.mocked(apiClient.listDirectory).mockResolvedValue({
      current_path: '/home/user/Documents',
      parent_path: '/home/user',
      directories: ['Work', 'Personal'],
    })

    fireEvent.doubleClick(screen.getByText('Documents'))

    await waitFor(() => {
      expect(apiClient.listDirectory).toHaveBeenCalledWith('/home/user/Documents')
    })
  })

  it('selects directory on click', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Documents')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Documents'))

    // Check that selected path is displayed
    await waitFor(() => {
      expect(screen.getByText('/home/user/Documents')).toBeInTheDocument()
    })
  })

  it('calls onSelect with selected directory path', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Documents')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Documents'))
    fireEvent.click(screen.getByRole('button', { name: 'Select' }))

    expect(mockOnSelect).toHaveBeenCalledWith('/home/user/Documents')
    expect(mockOnClose).toHaveBeenCalled()
  })

  it('calls onSelect with current directory if nothing selected', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Documents')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Select' }))

    expect(mockOnSelect).toHaveBeenCalledWith('/home/user')
    expect(mockOnClose).toHaveBeenCalled()
  })

  it('calls onClose when cancel is clicked', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Select Directory')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(mockOnClose).toHaveBeenCalled()
  })

  it('shows loading state', async () => {
    // Create a pending promise to keep loading state
    let resolvePromise: (value: unknown) => void
    const promise = new Promise((resolve) => {
      resolvePromise = resolve
    })
    vi.mocked(apiClient.listDirectory).mockReturnValue(promise as never)

    render(<DirectoryBrowserModal {...defaultProps} />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()

    // Resolve to cleanup
    resolvePromise!(mockDirectoryResponse)
  })

  it('shows error state', async () => {
    // Suppress console errors for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    vi.mocked(apiClient.listDirectory).mockRejectedValue(new Error('Access denied'))

    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('Access denied')).toBeInTheDocument()
    })

    consoleSpy.mockRestore()
  })

  it('shows empty directory message', async () => {
    vi.mocked(apiClient.listDirectory).mockResolvedValue({
      current_path: '/home/user/empty',
      parent_path: '/home/user',
      directories: [],
    })

    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('No subdirectories')).toBeInTheDocument()
    })
  })

  it('navigates to parent on go up click', async () => {
    render(<DirectoryBrowserModal {...defaultProps} />)

    await waitFor(() => {
      expect(screen.getByText('..')).toBeInTheDocument()
    })

    vi.mocked(apiClient.listDirectory).mockResolvedValue({
      current_path: '/home',
      parent_path: '/',
      directories: ['user', 'admin'],
    })

    fireEvent.click(screen.getByText('..'))

    await waitFor(() => {
      expect(apiClient.listDirectory).toHaveBeenCalledWith('/home')
    })
  })

  it('uses initialPath when provided', async () => {
    render(<DirectoryBrowserModal {...defaultProps} initialPath="/custom/path" />)

    await waitFor(() => {
      expect(apiClient.listDirectory).toHaveBeenCalledWith('/custom/path')
    })
  })
})
