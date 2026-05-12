import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import ChatDetailLayout from '../ChatDetailLayout'

// Mock CollapsedPanelStrip
vi.mock('../../ui/CollapsedPanelStrip', () => ({
  default: vi.fn(({ icon, label, onClick, isStreaming, needsAttention, variant, className }) => (
    <div
      data-testid={`collapsed-strip-${variant}`}
      onClick={onClick}
      className={className}
      data-streaming={isStreaming}
      data-attention={needsAttention}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </div>
  ))
}))

// ResizeObserver mock
let observeCallback: (entries: ResizeObserverEntry[]) => void

beforeEach(() => {
  vi.clearAllMocks()
  global.ResizeObserver = class {
    constructor(cb: ResizeObserverCallback) {
      observeCallback = cb as unknown as (entries: ResizeObserverEntry[]) => void
    }
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
})

const defaultProps = {
  chatContent: <div data-testid="chat-content">Chat Content</div>,
  detailsContent: <div data-testid="details-content">Details Content</div>,
  actionBar: <div data-testid="action-bar">Action Bar</div>,
  expandedPanel: 'chat' as const,
  onExpandPanel: vi.fn(),
  chatStripProps: { isStreaming: false, needsAttention: false },
  detailsStripProps: { needsAttention: false },
}

const triggerResize = (width: number) => {
  act(() => {
    observeCallback([{ contentRect: { width } } as ResizeObserverEntry])
  })
}

describe('ChatDetailLayout', () => {
  describe('Wide mode (container >= threshold)', () => {
    it('renders side-by-side layout with both panels visible', () => {
      render(<ChatDetailLayout {...defaultProps} />)
      triggerResize(1400)

      expect(screen.getByTestId('chat-content')).toBeInTheDocument()
      expect(screen.getByTestId('details-content')).toBeInTheDocument()
      expect(screen.getByTestId('action-bar')).toBeInTheDocument()

      expect(screen.queryByTestId('collapsed-strip-chat')).not.toBeInTheDocument()
      expect(screen.queryByTestId('collapsed-strip-details')).not.toBeInTheDocument()
    })

    it('renders draggable divider between panels', () => {
      const { container } = render(<ChatDetailLayout {...defaultProps} />)
      triggerResize(1400)

      const divider = container.querySelector('.cursor-col-resize')
      expect(divider).toBeInTheDocument()
    })

    it('renders panels with correct structure', () => {
      const { container } = render(<ChatDetailLayout {...defaultProps} />)
      triggerResize(1400)

      const root = container.firstChild as HTMLElement
      expect(root.children).toHaveLength(2) // panels layout + action bar

      const mainLayout = root.children[0]
      // Chat panel + divider + details panel
      expect(mainLayout.children).toHaveLength(3)
    })
  })

  describe('Narrow mode (container < threshold)', () => {
    it('renders collapsible layout with expanded panel visible', () => {
      render(<ChatDetailLayout {...defaultProps} expandedPanel="chat" />)
      triggerResize(800)

      expect(screen.getByTestId('chat-content')).toBeInTheDocument()
      expect(screen.getByTestId('details-content')).toBeInTheDocument()
      expect(screen.getByTestId('action-bar')).toBeInTheDocument()

      expect(screen.getByTestId('collapsed-strip-details')).toBeInTheDocument()
      expect(screen.queryByTestId('collapsed-strip-chat')).not.toBeInTheDocument()
    })

    it('shows correct collapsed strip when details expanded', () => {
      render(<ChatDetailLayout {...defaultProps} expandedPanel="details" />)
      triggerResize(800)

      expect(screen.getByTestId('collapsed-strip-chat')).toBeInTheDocument()
      expect(screen.queryByTestId('collapsed-strip-details')).not.toBeInTheDocument()
    })

    it('applies transition classes for collapsible panels', () => {
      const { container } = render(<ChatDetailLayout {...defaultProps} expandedPanel="chat" />)
      triggerResize(800)

      const panelElements = container.querySelectorAll('.transition-\\[flex\\].duration-200.ease-in-out')
      expect(panelElements).toHaveLength(2)
    })

    it('hides collapsed panel content with invisible class', () => {
      render(<ChatDetailLayout {...defaultProps} expandedPanel="chat" />)
      triggerResize(800)

      const detailsContent = screen.getByTestId('details-content')
      expect(detailsContent.parentElement).toHaveClass('invisible')

      const chatContent = screen.getByTestId('chat-content')
      expect(chatContent.parentElement).not.toHaveClass('invisible')
    })

    it('applies correct flex styles for expanded and collapsed panels', () => {
      const { container } = render(<ChatDetailLayout {...defaultProps} expandedPanel="details" />)
      triggerResize(800)

      const panels = container.querySelectorAll('.relative.h-full.overflow-hidden.transition-\\[flex\\]')
      expect(panels).toHaveLength(2)

      const [chatPanel, detailsPanel] = panels
      expect(chatPanel).toHaveStyle({ flex: '0 0 2.5rem' })
      expect(detailsPanel).toHaveStyle({ flex: '1 1 0%' })
    })
  })

  describe('Panel switching', () => {
    it('calls onExpandPanel when chat collapsed strip is clicked', () => {
      const onExpandPanel = vi.fn()
      render(<ChatDetailLayout {...defaultProps} expandedPanel="details" onExpandPanel={onExpandPanel} />)
      triggerResize(800)

      fireEvent.click(screen.getByTestId('collapsed-strip-chat'))
      expect(onExpandPanel).toHaveBeenCalledWith('chat')
    })

    it('calls onExpandPanel when details collapsed strip is clicked', () => {
      const onExpandPanel = vi.fn()
      render(<ChatDetailLayout {...defaultProps} expandedPanel="chat" onExpandPanel={onExpandPanel} />)
      triggerResize(800)

      fireEvent.click(screen.getByTestId('collapsed-strip-details'))
      expect(onExpandPanel).toHaveBeenCalledWith('details')
    })
  })

  describe('Strip props forwarding', () => {
    it('forwards chat strip props correctly', () => {
      render(
        <ChatDetailLayout
          {...defaultProps}
          expandedPanel="details"
          chatStripProps={{ isStreaming: true, needsAttention: true }}
        />
      )
      triggerResize(800)

      const chatStrip = screen.getByTestId('collapsed-strip-chat')
      expect(chatStrip).toHaveAttribute('data-streaming', 'true')
      expect(chatStrip).toHaveAttribute('data-attention', 'true')
    })

    it('forwards details strip props correctly', () => {
      render(
        <ChatDetailLayout
          {...defaultProps}
          expandedPanel="chat"
          detailsStripProps={{ needsAttention: true }}
        />
      )
      triggerResize(800)

      const detailsStrip = screen.getByTestId('collapsed-strip-details')
      expect(detailsStrip).toHaveAttribute('data-attention', 'true')
    })
  })

  describe('Narrow change callback', () => {
    it('calls onNarrowChange when crossing threshold', () => {
      const onNarrowChange = vi.fn()
      render(<ChatDetailLayout {...defaultProps} onNarrowChange={onNarrowChange} />)

      triggerResize(800)
      expect(onNarrowChange).toHaveBeenCalledWith(true)

      triggerResize(1400)
      expect(onNarrowChange).toHaveBeenCalledWith(false)
    })
  })

  describe('Action bar', () => {
    it('always renders action bar at bottom', () => {
      const { container } = render(<ChatDetailLayout {...defaultProps} />)
      triggerResize(1400)

      const root = container.firstChild as HTMLElement
      expect(root.lastChild).toHaveAttribute('data-testid', 'action-bar')
    })
  })
})
