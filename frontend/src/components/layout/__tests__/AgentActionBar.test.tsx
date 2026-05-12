import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import AgentActionBar from '../AgentActionBar'

// Mock the stream store for isQueued
vi.mock('../../../stores/conversationStreamStore', () => ({
  useConversationStreamStore: vi.fn((selector) => {
    // Default: isQueued = false, setQueued = noop
    if (typeof selector === 'function') {
      const mockState = {
        activeStreams: new Map(),
        setQueued: vi.fn(),
      }
      return selector(mockState)
    }
    return false
  }),
}))

// Mock the child components
vi.mock('../../chat/ConversationModelSelector', () => ({
  default: ({ conversationId, onModelChange }: {
    conversationId: number
    onModelChange?: (engine: string, modelId: string | null, modelName: string) => void
  }) => (
    <div data-testid="model-selector" data-conversation-id={conversationId}>
      Model Selector
      <button
        onClick={() => onModelChange?.('test_engine', 'test_model', 'Test Model')}
        data-testid="model-change-trigger"
      >
        Change Model
      </button>
    </div>
  )
}))

vi.mock('../../chat/ConversationInput', () => ({
  default: ({
    value,
    onChange,
    onSendMessage,
    placeholder,
    isStreaming,
    onStopStream,
    isQueued
  }: {
    value: string
    onChange: (value: string) => void
    onSendMessage: () => void
    placeholder?: string
    isStreaming?: boolean
    onStopStream?: () => void
    isQueued?: boolean
  }) => (
    <div data-testid="conversation-input">
      <input
        data-testid="input-field"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <button
        data-testid={isStreaming ? "stop-button" : "send-button"}
        onClick={isStreaming ? onStopStream : onSendMessage}
        disabled={!value.trim()}
      >
        {isStreaming ? 'Stop' : 'Send'}
      </button>
      {isQueued && <span data-testid="queued-indicator">Queued</span>}
    </div>
  )
}))

describe('AgentActionBar', () => {
  const defaultProps = {
    conversationId: 123 as number | null,
    onSendMessage: vi.fn(),
    isStreaming: false,
    onStopStream: vi.fn(),
    isDisabled: false,
    placeholder: 'Test placeholder',
    onModelChange: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all components when not disabled', () => {
    render(<AgentActionBar {...defaultProps} />)

    expect(screen.getByTestId('model-selector')).toBeInTheDocument()
    expect(screen.getByTestId('conversation-input')).toBeInTheDocument()
  })

  it('shows streaming indicator when isStreaming is true', () => {
    const { container } = render(<AgentActionBar {...defaultProps} isStreaming={true} />)

    // Pulsing green dot indicator
    expect(container.querySelector('.animate-ping')).toBeInTheDocument()
    expect(container.querySelector('.bg-green-500')).toBeInTheDocument()
  })

  it('dims model selector when streaming', () => {
    render(<AgentActionBar {...defaultProps} isStreaming={true} />)

    const modelSelectorWrapper = screen.getByTestId('model-selector').parentElement
    expect(modelSelectorWrapper).toHaveClass('opacity-50', 'pointer-events-none')
  })

  it('does not dim model selector when not streaming', () => {
    render(<AgentActionBar {...defaultProps} isStreaming={false} />)

    const modelSelectorWrapper = screen.getByTestId('model-selector').parentElement
    expect(modelSelectorWrapper).not.toHaveClass('opacity-50')
    expect(modelSelectorWrapper).not.toHaveClass('pointer-events-none')
  })

  it('shows disabled state when isDisabled is true', () => {
    render(<AgentActionBar {...defaultProps} isDisabled={true} disabledMessage="Custom disabled message" />)

    expect(screen.getByText('Custom disabled message')).toBeInTheDocument()
    expect(screen.queryByTestId('model-selector')).not.toBeInTheDocument()
    expect(screen.queryByTestId('conversation-input')).not.toBeInTheDocument()
  })

  it('shows default disabled message when none provided', () => {
    render(<AgentActionBar {...defaultProps} isDisabled={true} />)

    expect(screen.getByText('Chat is disabled')).toBeInTheDocument()
  })

  it('shows workflow actions and divider when provided', () => {
    const workflowActions = (
      <button data-testid="workflow-button">Create Plan</button>
    )

    render(<AgentActionBar {...defaultProps} workflowActions={workflowActions} />)

    expect(screen.getByTestId('workflow-button')).toBeInTheDocument()

    // Check for divider
    const divider = screen.getByTestId('workflow-button').closest('div')?.previousSibling
    expect(divider).toHaveClass('w-px', 'h-6', 'bg-gray-600')
  })

  it('does not show divider when no workflow actions', () => {
    render(<AgentActionBar {...defaultProps} />)

    const dividers = document.querySelectorAll('.w-px.h-6.bg-gray-600')
    expect(dividers).toHaveLength(0)
  })

  it('does not render model selector when conversationId is null', () => {
    render(<AgentActionBar {...defaultProps} conversationId={null} />)

    expect(screen.queryByTestId('model-selector')).not.toBeInTheDocument()
    expect(screen.getByTestId('conversation-input')).toBeInTheDocument()
  })

  it('renders input with placeholder and empty initial value', () => {
    render(<AgentActionBar {...defaultProps} placeholder="custom placeholder" />)

    const input = screen.getByTestId('input-field')
    expect(input).toHaveValue('')
    expect(input).toHaveAttribute('placeholder', 'custom placeholder')
  })

  it('updates internal input state when typing', () => {
    render(<AgentActionBar {...defaultProps} />)

    const input = screen.getByTestId('input-field')
    fireEvent.change(input, { target: { value: 'new message' } })

    expect(input).toHaveValue('new message')
  })

  it('calls onSendMessage with text and clears input when send button clicked', () => {
    render(<AgentActionBar {...defaultProps} />)

    const input = screen.getByTestId('input-field')
    fireEvent.change(input, { target: { value: 'test message' } })

    const sendButton = screen.getByTestId('send-button')
    fireEvent.click(sendButton)

    expect(defaultProps.onSendMessage).toHaveBeenCalledWith('test message')
    expect(input).toHaveValue('')
  })

  it('renders stop button during streaming', () => {
    render(<AgentActionBar {...defaultProps} isStreaming={true} />)

    // ConversationInput shows stop button when streaming
    expect(screen.getByTestId('stop-button')).toBeInTheDocument()
    expect(screen.queryByTestId('send-button')).not.toBeInTheDocument()
  })

  it('calls onModelChange when model selector triggers change', () => {
    render(<AgentActionBar {...defaultProps} />)

    const trigger = screen.getByTestId('model-change-trigger')
    fireEvent.click(trigger)

    expect(defaultProps.onModelChange).toHaveBeenCalledWith('test_engine', 'test_model', 'Test Model')
  })

  it('passes correct conversationId to model selector', () => {
    render(<AgentActionBar {...defaultProps} conversationId={456} />)

    const modelSelector = screen.getByTestId('model-selector')
    expect(modelSelector).toHaveAttribute('data-conversation-id', '456')
  })

  it('handles multiple workflow actions', () => {
    const workflowActions = (
      <div>
        <button data-testid="action-1">Action 1</button>
        <button data-testid="action-2">Action 2</button>
      </div>
    )

    render(<AgentActionBar {...defaultProps} workflowActions={workflowActions} />)

    expect(screen.getByTestId('action-1')).toBeInTheDocument()
    expect(screen.getByTestId('action-2')).toBeInTheDocument()
  })

  it('applies correct CSS classes for layout', () => {
    const { container } = render(<AgentActionBar {...defaultProps} />)

    const mainContainer = container.firstChild
    expect(mainContainer).toHaveClass('border', 'p-2', 'rounded-lg')

    const flexContainer = container.querySelector('.flex.items-center.gap-2')
    expect(flexContainer).toBeInTheDocument()
  })

  it('uses design system classes correctly', () => {
    const { container } = render(<AgentActionBar {...defaultProps} isDisabled={true} />)

    expect(container.querySelector('.text-center')).toBeInTheDocument()
  })
})
