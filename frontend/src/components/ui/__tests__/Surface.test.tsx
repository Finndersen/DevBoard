import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Surface from '../Surface'
import { surfaces, borderColors } from '../../../styles/designSystem'

describe('Surface', () => {
  it('renders raised variant with correct background', () => {
    const { container } = render(<Surface variant="raised">Content</Surface>)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain(surfaces.raised.split(' ')[0])
    expect(el.className).toContain('shadow-sm')
  })

  it('renders sunken variant with correct background', () => {
    const { container } = render(<Surface variant="sunken">Content</Surface>)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain(surfaces.sunken.split(' ')[0])
  })

  it('applies padding classes', () => {
    const { container } = render(<Surface variant="raised" padding="md">Content</Surface>)
    expect((container.firstChild as HTMLElement).className).toContain('p-6')
  })

  it('applies no padding when padding=none', () => {
    const { container } = render(<Surface variant="raised" padding="none">Content</Surface>)
    expect((container.firstChild as HTMLElement).className).not.toContain('p-')
  })

  it('includes rounded class by default', () => {
    const { container } = render(<Surface variant="raised">Content</Surface>)
    expect((container.firstChild as HTMLElement).className).toContain('rounded-lg')
  })

  it('omits rounded class when rounded=false', () => {
    const { container } = render(<Surface variant="raised" rounded={false}>Content</Surface>)
    expect((container.firstChild as HTMLElement).className).not.toContain('rounded-lg')
  })

  it('includes border by default', () => {
    const { container } = render(<Surface variant="raised">Content</Surface>)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain('border')
    expect(el.className).toContain(borderColors.default.split(' ')[0])
  })

  it('omits border when border=false', () => {
    const { container } = render(<Surface variant="raised" border={false}>Content</Surface>)
    expect((container.firstChild as HTMLElement).className).not.toContain('border')
  })

  it('supports className override', () => {
    const { container } = render(<Surface variant="raised" className="extra-class">Content</Surface>)
    expect((container.firstChild as HTMLElement).className).toContain('extra-class')
  })

  it('renders children', () => {
    const { getByText } = render(<Surface variant="sunken">Inner content</Surface>)
    expect(getByText('Inner content')).toBeInTheDocument()
  })

  it('renders with custom element type via as prop', () => {
    const { container } = render(<Surface variant="raised" as="section">Content</Surface>)
    expect(container.firstChild?.nodeName).toBe('SECTION')
  })
})
