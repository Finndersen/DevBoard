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

    await waitFor(() => {
      expect(screen.getByText('Mocked Diagram')).toBeInTheDocument()
    })
  })

  it('displays zoom controls', () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    expect(screen.getByLabelText('Zoom in')).toBeInTheDocument()
    expect(screen.getByLabelText('Zoom out')).toBeInTheDocument()
    expect(screen.getByLabelText('Reset view')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('updates zoom percentage when zooming in', async () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Zoom in'))

    expect(screen.getByText('125%')).toBeInTheDocument()
  })

  it('updates zoom percentage when zooming out', async () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Zoom out'))

    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('resets view when reset button is clicked', async () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Zoom in'))
    await user.click(screen.getByLabelText('Zoom in'))
    expect(screen.getByText('150%')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Reset view'))
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('hides source code by default', () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    expect(screen.getByText('Source Code')).toBeInTheDocument()
    expect(screen.queryByText('graph TD')).not.toBeInTheDocument()
  })

  it('shows source code when expanded', async () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    const user = userEvent.setup()
    await user.click(screen.getByText('Source Code'))

    await waitFor(() => {
      expect(screen.getByText(/graph/)).toBeInTheDocument()
    })
  })

  it('displays copy button', () => {
    renderWithProvider(
      <MermaidDiagramModal isOpen={true} onClose={mockOnClose} code={mockCode} />
    )

    expect(screen.getByText('Copy')).toBeInTheDocument()
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
