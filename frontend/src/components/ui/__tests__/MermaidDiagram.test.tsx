import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import MermaidDiagram from '../MermaidDiagram'
import { DarkModeProvider } from '../../../contexts/DarkModeContext'

const mockRender = vi.fn()

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: (...args: unknown[]) => mockRender(...args),
  },
}))

const renderWithProvider = (children: React.ReactNode) => {
  return render(
    <DarkModeProvider>
      {children}
    </DarkModeProvider>
  )
}

describe('MermaidDiagram', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRender.mockResolvedValue({ svg: '<svg data-testid="mock-svg">Rendered Diagram</svg>' })
  })

  it('renders loading state initially', () => {
    mockRender.mockImplementation(() => new Promise(() => {}))
    renderWithProvider(<MermaidDiagram code="graph TD\n  A --> B" />)
    expect(screen.getByText('Loading diagram...')).toBeInTheDocument()
  })

  it('renders mermaid diagram when successful', async () => {
    renderWithProvider(<MermaidDiagram code="graph TD\n  A --> B" />)

    await waitFor(() => {
      expect(screen.getByText('Rendered Diagram')).toBeInTheDocument()
    })
  })

  it('renders error state with source code when mermaid fails', async () => {
    mockRender.mockRejectedValue(new Error('Parse error: invalid syntax'))
    renderWithProvider(<MermaidDiagram code="invalid mermaid" />)

    await waitFor(() => {
      expect(screen.getByText('Diagram Error')).toBeInTheDocument()
      expect(screen.getByText('Parse error: invalid syntax')).toBeInTheDocument()
    })
  })

  it('calls onExpandClick with svg when diagram is clicked', async () => {
    const handleExpand = vi.fn()
    renderWithProvider(
      <MermaidDiagram code="graph TD\n  A --> B" onExpandClick={handleExpand} />
    )

    await waitFor(() => {
      expect(screen.getByText('Rendered Diagram')).toBeInTheDocument()
    })

    const user = userEvent.setup()
    const diagram = screen.getByRole('button')
    await user.click(diagram)

    expect(handleExpand).toHaveBeenCalledTimes(1)
    expect(handleExpand).toHaveBeenCalledWith('<svg data-testid="mock-svg">Rendered Diagram</svg>')
  })

  it('is not clickable when onExpandClick is not provided', async () => {
    renderWithProvider(<MermaidDiagram code="graph TD\n  A --> B" />)

    await waitFor(() => {
      expect(screen.getByText('Rendered Diagram')).toBeInTheDocument()
    })

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
