import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import HtmlPreview from '../HtmlPreview'
import { DarkModeProvider } from '../../../contexts/DarkModeContext'

const renderWithProvider = (children: React.ReactNode) => {
  return render(
    <DarkModeProvider>
      {children}
    </DarkModeProvider>
  )
}

describe('HtmlPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders an iframe with sandbox="allow-scripts" for HTML code', () => {
    renderWithProvider(<HtmlPreview code="<p>Hello</p>" language="html" />)
    const iframe = screen.getByTitle('HTML Preview')
    expect(iframe.tagName).toBe('IFRAME')
    expect(iframe).toHaveAttribute('sandbox', 'allow-scripts')
  })

  it('renders an iframe for SVG code', () => {
    renderWithProvider(
      <HtmlPreview code='<svg xmlns="http://www.w3.org/2000/svg"><rect /></svg>' language="svg" />
    )
    const iframe = screen.getByTitle('SVG Preview')
    expect(iframe.tagName).toBe('IFRAME')
    expect(iframe).toHaveAttribute('sandbox', 'allow-scripts')
  })

  it('defaults to Preview tab active', () => {
    renderWithProvider(<HtmlPreview code="<p>Hello</p>" language="html" />)
    expect(screen.getByTitle('HTML Preview')).toBeInTheDocument()
    expect(screen.getByText('Preview')).toBeInTheDocument()
    expect(screen.getByText('Source')).toBeInTheDocument()
  })

  it('switches to Source tab and renders CodeBlock', async () => {
    const user = userEvent.setup()
    renderWithProvider(<HtmlPreview code="<p>Hello</p>" language="html" />)

    await user.click(screen.getByText('Source'))

    expect(screen.queryByTitle('HTML Preview')).not.toBeInTheDocument()
    // CodeBlock renders a <pre><code> with the source
    expect(screen.getByText('<p>Hello</p>')).toBeInTheDocument()
  })

  it('displays correct language label for HTML', () => {
    renderWithProvider(<HtmlPreview code="<p>Hello</p>" language="html" />)
    expect(screen.getByText('HTML')).toBeInTheDocument()
  })

  it('displays correct language label for SVG', () => {
    renderWithProvider(
      <HtmlPreview code='<svg></svg>' language="svg" />
    )
    expect(screen.getByText('SVG')).toBeInTheDocument()
  })

  it('includes srcdoc with the user code', () => {
    renderWithProvider(<HtmlPreview code="<div>Test Content</div>" language="html" />)
    const iframe = screen.getByTitle('HTML Preview') as HTMLIFrameElement
    expect(iframe.srcdoc).toContain('<div>Test Content</div>')
    expect(iframe.srcdoc).toContain('__html_preview_resize')
  })

  it('updates height on postMessage from iframe', () => {
    renderWithProvider(<HtmlPreview code="<p>Hello</p>" language="html" />)
    const iframe = screen.getByTitle('HTML Preview') as HTMLIFrameElement

    fireEvent(window, new MessageEvent('message', {
      data: { type: '__html_preview_resize', height: 250 },
      source: iframe.contentWindow,
    }))

    expect(iframe.style.height).toBe('250px')
  })

  it('caps height at 500px', () => {
    renderWithProvider(<HtmlPreview code="<p>Hello</p>" language="html" />)
    const iframe = screen.getByTitle('HTML Preview') as HTMLIFrameElement

    fireEvent(window, new MessageEvent('message', {
      data: { type: '__html_preview_resize', height: 800 },
      source: iframe.contentWindow,
    }))

    expect(iframe.style.height).toBe('500px')
  })
})
