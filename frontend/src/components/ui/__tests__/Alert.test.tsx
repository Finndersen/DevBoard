import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Alert from '../Alert'
import { statusColors } from '../../../styles/designSystem'

describe('Alert', () => {
  it.each(['error', 'warning', 'info', 'success'] as const)('renders %s variant with correct status styling', (variant) => {
    const { container } = render(<Alert variant={variant}>Content</Alert>)
    const alertEl = container.firstChild as HTMLElement
    expect(alertEl.className).toContain(statusColors[variant].bg.split(' ')[0])
    expect(alertEl.className).toContain(statusColors[variant].border.split(' ')[0])
    expect(alertEl.className).toContain(statusColors[variant].text.split(' ')[0])
  })

  it('renders optional title', () => {
    render(<Alert variant="error" title="Something went wrong">Details</Alert>)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('renders children as content', () => {
    render(<Alert variant="info">Info message</Alert>)
    expect(screen.getByText('Info message')).toBeInTheDocument()
  })

  it('renders optional icon', () => {
    render(
      <Alert variant="success" icon={<span data-testid="custom-icon" />}>
        Done
      </Alert>
    )
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument()
  })

  it('supports className override', () => {
    const { container } = render(<Alert variant="error" className="my-custom-class">Error</Alert>)
    expect((container.firstChild as HTMLElement).className).toContain('my-custom-class')
  })

  it('renders without title when not provided', () => {
    render(<Alert variant="warning">Just content</Alert>)
    expect(screen.getByText('Just content')).toBeInTheDocument()
    expect(screen.queryByRole('paragraph')).toBeNull()
  })
})
