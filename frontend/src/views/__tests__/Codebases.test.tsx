import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import Codebases from '../Codebases'

// Mock data
const mockCodebases = [
  {
    id: 1,
    name: 'Test Codebase 1',
    description: 'First test codebase',
    local_path: '/path/to/codebase1',
    repository_url: 'https://github.com/test/repo1',
  },
  {
    id: 2,
    name: 'Test Codebase 2',
    description: 'Second test codebase',
    local_path: '/path/to/codebase2',
    repository_url: 'https://github.com/test/repo2',
  },
]

const mockArchitectureDocument = {
  exists: true,
  content: '# Architecture\n\nThis is a test architecture document.',
  content_hash: 'sha256:abc123def456',
  file_path: '/path/to/codebase1/ARCHITECTURE.md',
  size_bytes: 1024,
}

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('Codebases', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state initially', async () => {
    // Setup delayed response to test loading state
    server.use(
      http.get('*/api/codebases', async () => {
        await new Promise(resolve => setTimeout(resolve, 100))
        return HttpResponse.json(mockCodebases)
      })
    )

    renderWithRouter(<Codebases />)
    
    // Loading state shows a spinner, not text
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders empty state when no codebases exist', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([])
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('No codebases')).toBeInTheDocument()
    })
  })

  it('renders codebase dropdown and selects first codebase automatically', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json(mockCodebases)
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json(mockArchitectureDocument)
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Codebase 1')).toBeInTheDocument()
    })

    // Should automatically select and load first codebase
    await waitFor(() => {
      expect(screen.getByText('Test Codebase 1')).toBeInTheDocument()
      expect(screen.getByText('/path/to/codebase1')).toBeInTheDocument()
    })
  })

  it('switches between codebases when dropdown selection changes', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json(mockCodebases)
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json(mockArchitectureDocument)
      }),
      http.get('*/api/codebases/2/architecture_document/', () => {
        return HttpResponse.json({
          exists: false,
          content: null,
          content_hash: null,
          file_path: null,
          size_bytes: null,
        })
      })
    )

    renderWithRouter(<Codebases />)
    
    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Codebase 1')).toBeInTheDocument()
    })

    // Change selection to second codebase
    const dropdown = screen.getByDisplayValue('Test Codebase 1')
    fireEvent.change(dropdown, { target: { value: '2' } })

    await waitFor(() => {
      expect(screen.getByDisplayValue('Test Codebase 2')).toBeInTheDocument()
      expect(screen.getByText('Test Codebase 2')).toBeInTheDocument()
      expect(screen.getByText('/path/to/codebase2')).toBeInTheDocument()
    })
  })

  it('displays architecture document when it exists', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json(mockArchitectureDocument)
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Architecture')).toBeInTheDocument()
      expect(screen.getByText('This is a test architecture document.')).toBeInTheDocument()
    })
  })

  it('shows placeholder when architecture document does not exist', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json({
          exists: false,
          content: null,
          content_hash: null,
          file_path: null,
          size_bytes: null,
        })
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText(/No architecture document found/i)).toBeInTheDocument()
    })
  })

  it('enables editing mode when Edit button is clicked', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json(mockArchitectureDocument)
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Architecture')).toBeInTheDocument()
    })

    // Click edit button
    const editButton = screen.getByText('Edit')
    fireEvent.click(editButton)

    await waitFor(() => {
      expect(screen.getByDisplayValue('# Architecture\n\nThis is a test architecture document.')).toBeInTheDocument()
      expect(screen.getByText('Save')).toBeInTheDocument()
      expect(screen.getByText('Cancel')).toBeInTheDocument()
    })
  })

  it('cancels editing and restores original content', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json(mockArchitectureDocument)
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Architecture')).toBeInTheDocument()
    })

    // Enter edit mode
    const editButton = screen.getByText('Edit')
    fireEvent.click(editButton)

    await waitFor(() => {
      const textarea = screen.getByDisplayValue('# Architecture\n\nThis is a test architecture document.')
      // Modify content
      fireEvent.change(textarea, { target: { value: '# Modified Content' } })
      expect(screen.getByDisplayValue('# Modified Content')).toBeInTheDocument()
    })

    // Cancel editing
    const cancelButton = screen.getByText('Cancel')
    fireEvent.click(cancelButton)

    await waitFor(() => {
      // Should restore original content
      expect(screen.getByText('This is a test architecture document.')).toBeInTheDocument()
      expect(screen.getByText('Edit')).toBeInTheDocument()
    })
  })

  it('saves architecture document successfully', async () => {
    const updatedContent = '# Updated Architecture\n\nThis is updated content.'
    
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json(mockArchitectureDocument)
      }),
      http.put('*/api/codebases/1/architecture_document/', async ({ request }) => {
        const body = await request.json() as { content: string; original_hash: string }
        expect(body.content).toBe(updatedContent)
        expect(body.original_hash).toBe('sha256:abc123def456')
        
        return HttpResponse.json({
          success: true,
          content_hash: 'sha256:new123hash456',
        })
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json({
          ...mockArchitectureDocument,
          content: updatedContent,
          content_hash: 'sha256:new123hash456',
        })
      }, { once: true })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Architecture')).toBeInTheDocument()
    })

    // Enter edit mode
    const editButton = screen.getByText('Edit')
    fireEvent.click(editButton)

    await waitFor(() => {
      const textarea = screen.getByDisplayValue('# Architecture\n\nThis is a test architecture document.')
      fireEvent.change(textarea, { target: { value: updatedContent } })
    })

    // Save changes
    const saveButton = screen.getByText('Save')
    fireEvent.click(saveButton)

    await waitFor(() => {
      // Should exit edit mode and show updated content
      expect(screen.getByText('Updated Architecture')).toBeInTheDocument()
      expect(screen.getByText('This is updated content.')).toBeInTheDocument()
      expect(screen.getByText('Edit')).toBeInTheDocument()
    })
  })

  it('handles save conflict by showing error and keeping edit mode active', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json(mockArchitectureDocument)
      }),
      http.put('*/api/codebases/1/architecture_document/', () => {
        return new HttpResponse(
          JSON.stringify({
            detail: 'Content conflict detected: file was modified externally',
            current_hash: 'sha256:different123hash456',
          }),
          { status: 409 }
        )
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Architecture')).toBeInTheDocument()
    })

    // Enter edit mode and modify content
    const editButton = screen.getByText('Edit')
    fireEvent.click(editButton)

    await waitFor(() => {
      const textarea = screen.getByDisplayValue('# Architecture\n\nThis is a test architecture document.')
      fireEvent.change(textarea, { target: { value: '# Modified Content' } })
    })

    // Try to save
    const saveButton = screen.getByText('Save')
    fireEvent.click(saveButton)

    await waitFor(() => {
      // Should show error message and remain in edit mode
      expect(screen.getByText(/conflict detected/i)).toBeInTheDocument()
      expect(screen.getByDisplayValue('# Modified Content')).toBeInTheDocument()
      expect(screen.getByText('Save')).toBeInTheDocument()
      expect(screen.getByText('Cancel')).toBeInTheDocument()
    })
  })

  it('generates architecture document successfully', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json({
          exists: false,
          content: null,
          content_hash: null,
          file_path: null,
          size_bytes: null,
        })
      }),
      http.post('*/api/codebases/1/architecture_document/generate', () => {
        return HttpResponse.json({
          success: true,
          file_path: '/path/to/codebase1/ARCHITECTURE.md',
        })
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        return HttpResponse.json({
          exists: true,
          content: '# Generated Architecture\n\nThis document was generated by AI.',
          content_hash: 'sha256:generated123hash456',
          file_path: '/path/to/codebase1/ARCHITECTURE.md',
          size_bytes: 512,
        })
      }, { once: true })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText(/No architecture document found/i)).toBeInTheDocument()
    })

    // Click generate button
    const generateButton = screen.getByText('Generate with AI')
    fireEvent.click(generateButton)

    await waitFor(() => {
      // Should show generated content
      expect(screen.getByText('Generated Architecture')).toBeInTheDocument()
      expect(screen.getByText('This document was generated by AI.')).toBeInTheDocument()
    })
  })

  it('handles API errors gracefully', async () => {
    server.use(
      http.get('*/api/codebases', () => {
        return new HttpResponse(null, { status: 500, statusText: 'Internal Server Error' })
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch codebases')).toBeInTheDocument()
    })
  })
})