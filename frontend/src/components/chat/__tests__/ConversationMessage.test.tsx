import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '../../../test/utils'
import ConversationMessageComponent from '../ConversationMessage'
import type { ConversationMessage, ToolCall, ToolResult, ToolCallRequest } from '../../../lib/api'

// Mock the Markdown and ToolCallDisplay components
vi.mock('../../ui', () => ({
  Markdown: ({ children, forceWhiteText }: { children: string; forceWhiteText?: boolean }) => (
    <div data-testid="markdown" data-force-white-text={forceWhiteText}>
      {children}
    </div>
  ),
}))

vi.mock('../ToolCallDisplay', () => ({
  default: ({ toolCall, toolResult }: { toolCall: ToolCall; toolResult?: ToolResult }) => (
    <div data-testid="tool-call-display">
      <span data-testid="tool-call-id">{toolCall.tool_call_id}</span>
      <span data-testid="tool-name">{toolCall.tool_name}</span>
      {toolResult && <span data-testid="tool-result-id">{toolResult.tool_call_id}</span>}
    </div>
  ),
}))

describe('ConversationMessage', () => {
  describe('message events', () => {
    it('renders user message with correct styling (blue bubble)', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Hello, how are you?',
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={userMessage} />)

      const messageText = screen.getByText('Hello, how are you?')
      expect(messageText).toBeInTheDocument()

      // Check that the message is inside a blue bubble
      const messageBubble = screen.getByTestId('markdown').closest('.bg-blue-600')
      expect(messageBubble).toBeInTheDocument()
      expect(messageBubble).toHaveClass('text-white')

      // Check alignment (user messages should be right-aligned)
      const container = messageBubble?.closest('.justify-end')
      expect(container).toBeInTheDocument()
    })

    it('renders agent message with correct styling (gray bubble)', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'I am doing well, thank you!',
        timestamp: '2024-01-01T10:01:00Z',
      }

      render(<ConversationMessageComponent message={agentMessage} />)

      const messageText = screen.getByText('I am doing well, thank you!')
      expect(messageText).toBeInTheDocument()

      // Check that the message is inside a gray bubble (note: uses dark mode classes)
      const markdownElement = screen.getByTestId('markdown')
      const messageBubble = markdownElement.closest('.bg-gray-100')
      expect(messageBubble).toBeInTheDocument()

      // Check alignment (agent messages should be left-aligned)
      const container = messageBubble?.closest('.justify-start')
      expect(container).toBeInTheDocument()
    })

    it('passes forceWhiteText prop to Markdown for user messages', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Test message',
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={userMessage} />)

      const markdown = screen.getByTestId('markdown')
      expect(markdown).toHaveAttribute('data-force-white-text', 'true')
    })

    it('does not pass forceWhiteText prop to Markdown for agent messages', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'Test message',
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={agentMessage} />)

      const markdown = screen.getByTestId('markdown')
      expect(markdown).toHaveAttribute('data-force-white-text', 'false')
    })

    it('displays timestamp for user messages', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Test message',
        timestamp: '2024-01-01T15:30:00Z',
      }

      render(<ConversationMessageComponent message={userMessage} />)

      // Should display formatted timestamp (exact format depends on locale)
      const timestamp = screen.getByText(/\d{1,2}:\d{2}/)
      expect(timestamp).toBeInTheDocument()
      expect(timestamp).toHaveClass('text-xs', 'opacity-70')
    })

    it('displays timestamp for agent messages', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'Test message',
        timestamp: '2024-01-01T15:30:00Z',
      }

      render(<ConversationMessageComponent message={agentMessage} />)

      // Should display formatted timestamp
      const timestamp = screen.getByText(/\d{1,2}:\d{2}/)
      expect(timestamp).toBeInTheDocument()
      expect(timestamp).toHaveClass('text-xs', 'opacity-70')
    })

    it('renders multi-line message content', () => {
      const message: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Line 1\nLine 2\nLine 3',
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={message} />)

      const markdown = screen.getByTestId('markdown')
      // Note: textContent in DOM doesn't preserve newlines the same way as raw text
      // Just check that the content is present
      expect(markdown.textContent).toContain('Line 1')
      expect(markdown.textContent).toContain('Line 2')
      expect(markdown.textContent).toContain('Line 3')
    })

    it('renders empty message content', () => {
      const message: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: '',
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={message} />)

      const markdown = screen.getByTestId('markdown')
      expect(markdown).toHaveTextContent('')
    })
  })

  describe('tool_call events', () => {
    it('renders tool_call event using ToolCallDisplay component', () => {
      const toolCall: ToolCall = {
        event_type: 'tool_call',
        tool_call_id: 'call_123',
        tool_name: 'test_tool',
        tool_args: { arg1: 'value1' },
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCall} />)

      expect(screen.getByTestId('tool-call-display')).toBeInTheDocument()
      expect(screen.getByTestId('tool-call-id')).toHaveTextContent('call_123')
      expect(screen.getByTestId('tool-name')).toHaveTextContent('test_tool')
    })

    it('passes toolResult to ToolCallDisplay when provided', () => {
      const toolCall: ToolCall = {
        event_type: 'tool_call',
        tool_call_id: 'call_123',
        tool_name: 'test_tool',
        tool_args: { arg1: 'value1' },
        timestamp: '2024-01-01T10:00:00Z',
      }

      const toolResult: ToolResult = {
        event_type: 'tool_result',
        tool_call_id: 'call_123',
        result_content: 'Success',
        is_error: false,
        timestamp: '2024-01-01T10:01:00Z',
      }

      render(<ConversationMessageComponent message={toolCall} toolResult={toolResult} />)

      expect(screen.getByTestId('tool-call-display')).toBeInTheDocument()
      expect(screen.getByTestId('tool-result-id')).toHaveTextContent('call_123')
    })

    it('renders tool_call without toolResult', () => {
      const toolCall: ToolCall = {
        event_type: 'tool_call',
        tool_call_id: 'call_456',
        tool_name: 'another_tool',
        tool_args: null,
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCall} />)

      expect(screen.getByTestId('tool-call-display')).toBeInTheDocument()
      expect(screen.queryByTestId('tool-result-id')).not.toBeInTheDocument()
    })
  })

  describe('tool_result events', () => {
    it('returns null for tool_result events (not rendered standalone)', () => {
      const toolResult: ToolResult = {
        event_type: 'tool_result',
        tool_call_id: 'call_123',
        result_content: 'Success',
        is_error: false,
        timestamp: '2024-01-01T10:01:00Z',
      }

      const { container } = render(<ConversationMessageComponent message={toolResult} />)

      // Should render nothing
      expect(container.firstChild).toBeNull()
    })
  })

  describe('tool_call_request events', () => {
    it('renders tool_call_request with approval UI and yellow styling', () => {
      const toolCallRequest: ToolCallRequest = {
        event_type: 'tool_call_request',
        tool_call_id: 'request_123',
        tool_name: 'edit_project_specification',
        tool_args: { edits: [{ find: 'old', replace: 'new' }] },
        timestamp: '2025-01-20T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCallRequest} />)

      // Check for yellow styling classes on the outer card
      const awaitingText = screen.getByText(/Awaiting Approval/i)
      const cardElement = awaitingText.closest('.rounded-lg')
      expect(cardElement).toBeInTheDocument()
      expect(cardElement).toHaveClass('border-yellow-600')
      expect(cardElement).toHaveClass('bg-yellow-900/10')

      // Check for warning icon (SVG)
      const svg = awaitingText.parentElement?.querySelector('svg')
      expect(svg).toBeInTheDocument()
      expect(svg).toHaveClass('text-yellow-400')
    })

    it('shows tool name in tool_call_request header', () => {
      const toolCallRequest: ToolCallRequest = {
        event_type: 'tool_call_request',
        tool_call_id: 'request_456',
        tool_name: 'create_new_task',
        tool_args: null,
        timestamp: '2025-01-20T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCallRequest} />)

      expect(screen.getByText('Awaiting Approval: create_new_task')).toBeInTheDocument()
    })

    it('displays tool arguments for tool_call_request when provided as object', () => {
      const toolCallRequest: ToolCallRequest = {
        event_type: 'tool_call_request',
        tool_call_id: 'request_789',
        tool_name: 'update_document',
        tool_args: {
          file: 'test.md',
          content: 'New content'
        },
        timestamp: '2025-01-20T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCallRequest} />)

      expect(screen.getByText('Arguments:')).toBeInTheDocument()

      // Check that arguments are displayed as formatted JSON
      const argsContainer = screen.getByText('Arguments:').parentElement
      const preElement = argsContainer?.querySelector('pre')
      expect(preElement).toBeInTheDocument()
      expect(preElement?.textContent).toContain('"file"')
      expect(preElement?.textContent).toContain('"content"')
    })

    it('does not display arguments for tool_call_request when provided as string', () => {
      const toolCallRequest: ToolCallRequest = {
        event_type: 'tool_call_request',
        tool_call_id: 'request_999',
        tool_name: 'execute_command',
        tool_args: 'some string argument',
        timestamp: '2025-01-20T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCallRequest} />)

      // String arguments don't satisfy the condition: typeof === 'object' && Object.keys().length > 0
      // So they won't display the arguments section
      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
    })

    it('does not display arguments section when tool_args is null', () => {
      const toolCallRequest: ToolCallRequest = {
        event_type: 'tool_call_request',
        tool_call_id: 'request_000',
        tool_name: 'simple_tool',
        tool_args: null,
        timestamp: '2025-01-20T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCallRequest} />)

      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
    })

    it('does not display arguments section when tool_args is empty object', () => {
      const toolCallRequest: ToolCallRequest = {
        event_type: 'tool_call_request',
        tool_call_id: 'request_111',
        tool_name: 'simple_tool',
        tool_args: {},
        timestamp: '2025-01-20T10:00:00Z',
      }

      render(<ConversationMessageComponent message={toolCallRequest} />)

      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
    })

    it('renders approval UI container with correct structure', () => {
      const toolCallRequest: ToolCallRequest = {
        event_type: 'tool_call_request',
        tool_call_id: 'request_222',
        tool_name: 'test_tool',
        tool_args: null,
        timestamp: '2025-01-20T10:00:00Z',
      }

      const { container } = render(<ConversationMessageComponent message={toolCallRequest} />)

      // Check for proper container structure
      const outerContainer = container.querySelector('.justify-start')
      expect(outerContainer).toBeInTheDocument()

      const innerContainer = outerContainer?.querySelector('.max-w-\\[80\\%\\]')
      expect(innerContainer).toBeInTheDocument()

      const card = innerContainer?.querySelector('.rounded-lg')
      expect(card).toBeInTheDocument()
    })
  })

  describe('unknown event types', () => {
    it('returns null for unknown event types', () => {
      const unknownEvent = {
        event_type: 'unknown_type',
        data: 'some data',
      } as unknown as ConversationMessage

      const { container } = render(<ConversationMessageComponent message={unknownEvent} />)

      // Should render nothing
      expect(container.firstChild).toBeNull()
    })
  })
})
