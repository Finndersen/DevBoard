import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import TableOfContentsPopover from '../TableOfContentsPopover'
import type { TocHeading } from '../../../utils/markdown'

const sampleHeadings: TocHeading[] = [
  { level: 2, text: 'Introduction', slug: 'introduction' },
  { level: 2, text: 'Getting Started', slug: 'getting-started' },
  { level: 3, text: 'Installation', slug: 'installation' },
]

function renderPopover(headings = sampleHeadings) {
  const scrollContainerRef = createRef<HTMLDivElement>()
  const result = render(
    <div ref={scrollContainerRef}>
      <TableOfContentsPopover headings={headings} scrollContainerRef={scrollContainerRef} />
    </div>,
  )
  return result
}

describe('TableOfContentsPopover', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Contents trigger button', () => {
    renderPopover()
    expect(screen.getByRole('button', { name: /contents/i })).toBeInTheDocument()
  })

  it('opens popover on click and shows all headings', async () => {
    const user = userEvent.setup()
    renderPopover()

    await user.click(screen.getByRole('button', { name: /contents/i }))

    expect(screen.getByText('Introduction')).toBeInTheDocument()
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
    expect(screen.getByText('Installation')).toBeInTheDocument()
  })

  it('closes popover on Escape key', async () => {
    const user = userEvent.setup()
    renderPopover()

    await user.click(screen.getByRole('button', { name: /contents/i }))
    expect(screen.getByText('Introduction')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    expect(screen.queryByText('Introduction')).not.toBeInTheDocument()
  })

  it('closes popover on click outside', async () => {
    const user = userEvent.setup()
    renderPopover()

    await user.click(screen.getByRole('button', { name: /contents/i }))
    expect(screen.getByText('Introduction')).toBeInTheDocument()

    fireEvent.mouseDown(document.body)

    expect(screen.queryByText('Introduction')).not.toBeInTheDocument()
  })

  it('calls scrollIntoView on heading click and closes popover', async () => {
    const user = userEvent.setup()
    const scrollContainerRef = createRef<HTMLDivElement>()
    render(
      <div ref={scrollContainerRef}>
        <TableOfContentsPopover headings={sampleHeadings} scrollContainerRef={scrollContainerRef} />
      </div>,
    )

    await user.click(screen.getByRole('button', { name: /contents/i }))

    const targetElement = document.createElement('div')
    targetElement.id = 'introduction'
    targetElement.scrollIntoView = vi.fn()

    const containerEl = scrollContainerRef.current!
    const originalQuerySelector = containerEl.querySelector.bind(containerEl)
    vi.spyOn(containerEl, 'querySelector').mockImplementation((selector: string) => {
      if (selector === `#introduction`) return targetElement
      return originalQuerySelector(selector)
    })

    await user.click(screen.getByText('Introduction'))

    expect(targetElement.scrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'start',
    })
    expect(screen.queryByText('Getting Started')).not.toBeInTheDocument()
  })
})
