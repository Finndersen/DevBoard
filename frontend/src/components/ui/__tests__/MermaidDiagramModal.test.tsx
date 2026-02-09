import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import MermaidDiagramModal from '../MermaidDiagramModal'
import { DarkModeProvider } from '../../../contexts/DarkModeContext'

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg>Mocked Diagram</svg>' }),
  },
}))

const renderWithProvider = (children: React.ReactNode) => {
  return render(
    <DarkModeProvider>
      {children}
    </DarkModeProvider>
  )
}

describe('MermaidDiagramModal', () => {
  const mockCode = 'graph TD\n  A --> B'
  const mockOnClose = vi.fn()
  const mockWriteText = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockWriteText.mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: mockWriteText },
      writable: true,
      configurable: true,
    })
  })

  it('does not render when isOpen is false', () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={false} onClose={mockOnClose} code={mockCode} />
    )
    expect(screen.queryByText('Mermaid Diagram')).not.toBeInTheDocument()
  })

  it('renders modal when isOpen is true', async () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )
    expect(screen.getByText('Mermaid Diagram')).toBeInTheDocument()
    expect(screen.getByText('Source Code')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Mocked Diagram')).toBeInTheDocument()
    })
  })

  it('displays copy source button', async () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    expect(screen.getByText('Copy Source')).toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', async () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    const user = userEvent.setup()
    const closeButton = screen.getByRole('button', { name: /close modal/i })
    await user.click(closeButton)

    expect(mockOnClose).toHaveBeenCalledTimes(1)
  })
})
