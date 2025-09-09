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
      const dropdown = screen.getByRole('combobox')
      expect(dropdown).toHaveValue('1')
    })

    // Should automatically select and load first codebase
    await waitFor(() => {
      expect(screen.getByText('Test Codebase 1')).toBeInTheDocument()
      expect(screen.getAllByText('/path/to/codebase1')).toHaveLength(2) // Header and Local Path section
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
      const dropdown = screen.getByRole('combobox')
      expect(dropdown).toHaveValue('1')
    })

    // Change selection to second codebase
    const dropdown = screen.getByRole('combobox')
    fireEvent.change(dropdown, { target: { value: '2' } })

    await waitFor(() => {
      const dropdown = screen.getByRole('combobox')
      expect(dropdown).toHaveValue('2')
      expect(screen.getByText('Test Codebase 2')).toBeInTheDocument()
      expect(screen.getAllByText('/path/to/codebase2')).toHaveLength(2) // Header and Local Path section
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

    // Wait for architecture document to load, then click edit
    await waitFor(() => {
      expect(screen.getByText('ARCHITECTURE.md exists')).toBeInTheDocument()
    })

    // Click architecture edit button 
    const editButtons = screen.getAllByText('Edit')
    expect(editButtons).toHaveLength(2) // Codebase edit and architecture edit
    const architectureEditButton = editButtons[1] 
    fireEvent.click(architectureEditButton)

    await waitFor(() => {
      const textarea = screen.getByRole('textbox')
      expect(textarea).toHaveValue('# Architecture\n\nThis is a test architecture document.')
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

    // Wait for architecture document to load, then click edit
    await waitFor(() => {
      expect(screen.getByText('ARCHITECTURE.md exists')).toBeInTheDocument()
    })

    // Enter edit mode
    const editButtons = screen.getAllByText('Edit')
    const architectureEditButton = editButtons[1] // Second Edit button is for architecture
    fireEvent.click(architectureEditButton)

    await waitFor(() => {
      const textarea = screen.getByRole('textbox')
      expect(textarea).toHaveValue('# Architecture\n\nThis is a test architecture document.')
      // Modify content
      fireEvent.change(textarea, { target: { value: '# Modified Content' } })
      expect(textarea).toHaveValue('# Modified Content')
    })

    // Cancel editing
    const cancelButton = screen.getByText('Cancel')
    fireEvent.click(cancelButton)

    await waitFor(() => {
      // Should restore original content
      expect(screen.getByText('This is a test architecture document.')).toBeInTheDocument()
      expect(screen.getAllByText('Edit')).toHaveLength(2) // Back to showing both edit buttons
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

    // Wait for architecture document to load, then click edit
    await waitFor(() => {
      expect(screen.getByText('ARCHITECTURE.md exists')).toBeInTheDocument()
    })

    // Enter edit mode
    const editButtons = screen.getAllByText('Edit')
    const architectureEditButton = editButtons[1] // Second Edit button is for architecture
    fireEvent.click(architectureEditButton)

    await waitFor(() => {
      const textarea = screen.getByRole('textbox')
      expect(textarea).toHaveValue('# Architecture\n\nThis is a test architecture document.')
      fireEvent.change(textarea, { target: { value: updatedContent } })
    })

    // Save changes
    const saveButton = screen.getByText('Save')
    fireEvent.click(saveButton)

    await waitFor(() => {
      // Should exit edit mode and show updated content
      expect(screen.getByText('Updated Architecture')).toBeInTheDocument()
      expect(screen.getByText('This is updated content.')).toBeInTheDocument()
      expect(screen.getAllByText('Edit')).toHaveLength(2) // Should show both edit buttons again
    })
  })

  it.skip('handles save conflict by showing error and keeping edit mode active', async () => {
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
            message: 'Content conflict detected: file was modified externally',
            current_hash: 'sha256:different123hash456',
          }),
          { status: 409, statusText: 'Conflict' }
        )
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Architecture')).toBeInTheDocument()
    })

    // Wait for architecture document to load, then click edit
    await waitFor(() => {
      expect(screen.getByText('ARCHITECTURE.md exists')).toBeInTheDocument()
    })

    // Enter edit mode and modify content
    const editButtons = screen.getAllByText('Edit')
    const architectureEditButton = editButtons[1] // Second Edit button is for architecture
    fireEvent.click(architectureEditButton)

    await waitFor(() => {
      const textarea = screen.getByRole('textbox')
      expect(textarea).toHaveValue('# Architecture\n\nThis is a test architecture document.')
      fireEvent.change(textarea, { target: { value: '# Modified Content' } })
    })

    // Try to save
    const saveButton = screen.getByText('Save')
    fireEvent.click(saveButton)

    await waitFor(() => {
      // Should show error message and remain in edit mode - let's check for any error in the DOM
      const errorElements = screen.queryAllByText(/.*/)
      const hasError = errorElements.some(el => 
        el.textContent?.includes('error') || 
        el.textContent?.includes('conflict') ||
        el.textContent?.includes('failed')
      )
      expect(hasError).toBe(true)
      
      const textarea = screen.getByRole('textbox')
      expect(textarea).toHaveValue('# Modified Content')
      expect(screen.getByText('Save')).toBeInTheDocument()
      expect(screen.getByText('Cancel')).toBeInTheDocument()
    })
  })

  it('generates architecture document successfully', async () => {
    let architectureGetCallCount = 0
    
    server.use(
      http.get('*/api/codebases', () => {
        return HttpResponse.json([mockCodebases[0]])
      }),
      http.get('*/api/codebases/1/architecture_document/', () => {
        architectureGetCallCount++
        if (architectureGetCallCount === 1) {
          // First call - no document exists
          return HttpResponse.json({
            exists: false,
            content: null,
            content_hash: null,
            file_path: null,
            size_bytes: null,
          })
        } else {
          // After generation - document exists
          return HttpResponse.json({
            exists: true,
            content: '# Generated Architecture\n\nThis document was generated by AI.',
            content_hash: 'sha256:generated123hash456',
            file_path: '/path/to/codebase1/ARCHITECTURE.md',
            size_bytes: 512,
          })
        }
      }),
      http.post('*/api/codebases/1/architecture_document/generate', () => {
        return HttpResponse.json({
          success: true,
          file_path: '/path/to/codebase1/ARCHITECTURE.md',
        })
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText(/No architecture document found/i)).toBeInTheDocument()
    })

    // Click generate button
    const generateButton = screen.getByText('Generate')
    fireEvent.click(generateButton)

    // Wait for generation to complete and document to be fetched
    await waitFor(() => {
      expect(screen.getByText('Generated Architecture')).toBeInTheDocument()
      expect(screen.getByText('This document was generated by AI.')).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it('handles API errors gracefully', async () => {
    // Suppress console errors for this test
    const originalConsoleError = console.error
    console.error = vi.fn()
    
    server.use(
      http.get('*/api/codebases', () => {
        return new HttpResponse(null, { status: 500, statusText: 'Internal Server Error' })
      })
    )

    renderWithRouter(<Codebases />)
    
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch codebases')).toBeInTheDocument()
    })
    
    // Restore console.error
    console.error = originalConsoleError
  })
})