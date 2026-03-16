import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Markdown from '../Markdown'
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

describe('Markdown', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders basic markdown text', () => {
    renderWithProvider(<Markdown>Hello **world**</Markdown>)
    expect(screen.getByText('world')).toBeInTheDocument()
  })

  it('renders inline code without syntax highlighting', () => {
    renderWithProvider(<Markdown>Use `console.log` here</Markdown>)
    const code = screen.getByText('console.log')
    expect(code.tagName).toBe('CODE')
  })

  it('renders code blocks with syntax highlighting', () => {
    const markdown = '```javascript\nconst x = 1;\n```'
    renderWithProvider(<Markdown>{markdown}</Markdown>)
    expect(screen.getByText(/const/)).toBeInTheDocument()
  })

  it('renders mermaid diagrams', async () => {
    const markdown = '```mermaid\ngraph TD\n  A --> B\n```'
    renderWithProvider(<Markdown>{markdown}</Markdown>)

    await vi.waitFor(() => {
      expect(screen.getByText('Mocked Diagram')).toBeInTheDocument()
    })
  })

  it('applies forceWhiteText class when prop is true', () => {
    const { container } = renderWithProvider(
      <Markdown forceWhiteText>Test</Markdown>
    )
    expect(container.firstChild).toHaveClass('prose-invert')
  })

  it('renders html code blocks as HtmlPreview', () => {
    const markdown = '```html\n<div>Hello</div>\n```'
    renderWithProvider(<Markdown>{markdown}</Markdown>)
    const iframe = screen.getByTitle('HTML Preview')
    expect(iframe).toBeInTheDocument()
    expect(iframe).toHaveAttribute('sandbox', 'allow-scripts')
  })

  it('renders svg code blocks as HtmlPreview', () => {
    const markdown = '```svg\n<svg><rect /></svg>\n```'
    renderWithProvider(<Markdown>{markdown}</Markdown>)
    const iframe = screen.getByTitle('SVG Preview')
    expect(iframe).toBeInTheDocument()
    expect(iframe).toHaveAttribute('sandbox', 'allow-scripts')
  })

  it('applies custom className', () => {
    const { container } = renderWithProvider(
      <Markdown className="custom-class">Test</Markdown>
    )
    expect(container.firstChild).toHaveClass('custom-class')
  })

  describe('heading IDs', () => {
    it('adds id attributes to rendered headings', () => {
      const { container } = renderWithProvider(
        <Markdown>## Hello World</Markdown>
      )
      const h2 = container.querySelector('h2')
      expect(h2).toHaveAttribute('id', 'hello-world')
    })

    it('adds suffixed ids for duplicate headings', () => {
      const { container } = renderWithProvider(
        <Markdown>{'## Section\n\n## Section'}</Markdown>
      )
      const headings = container.querySelectorAll('h2')
      expect(headings).toHaveLength(2)
      expect(headings[0]).toHaveAttribute('id', 'section')
      expect(headings[1]).toHaveAttribute('id', 'section-1')
    })
  })
})
