import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import ConversationMessageComponent from '../ConversationMessage'
import type { ConversationMessage, ToolCall, ToolResult, ToolCallRequest, SystemEvent, ThinkingEvent } from '../../../lib/api'

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
    it('renders user message with correct styling (subtle background)', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Hello, how are you?',
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={userMessage} />)

      const messageText = screen.getByText('Hello, how are you?')
      expect(messageText).toBeInTheDocument()

      // Check that the message has a subtle full-width background
      const messageContainer = screen.getByTestId('markdown').closest('.bg-gray-100')
      expect(messageContainer).toBeInTheDocument()
      expect(messageContainer).toHaveClass('w-full')
    })

    it('renders agent message as plain text without bubble', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'I am doing well, thank you!',
        timestamp: '2024-01-01T10:01:00Z',
      }

      render(<ConversationMessageComponent message={agentMessage} />)

      const messageText = screen.getByText('I am doing well, thank you!')
      expect(messageText).toBeInTheDocument()

      // Agent messages should render as plain text — no background styling
      const markdownElement = screen.getByTestId('markdown')
      expect(markdownElement.closest('.bg-blue-600')).not.toBeInTheDocument()
    })

    it('does not force white text for user messages', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Test message',
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={userMessage} />)

      const markdown = screen.getByTestId('markdown')
      expect(markdown).toHaveAttribute('data-force-white-text', 'false')
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
      // Agent messages do not pass forceWhiteText — attribute should not be present
      expect(markdown).not.toHaveAttribute('data-force-white-text', 'true')
    })

    it('handles user messages with timestamps', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Test message',
        timestamp: '2024-01-01T15:30:00Z',
      }

      render(<ConversationMessageComponent message={userMessage} />)

      // Message should render (timestamps are not displayed in the current implementation)
      expect(screen.getByText('Test message')).toBeInTheDocument()
    })

    it('handles agent messages with timestamps', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'Test message',
        timestamp: '2024-01-01T15:30:00Z',
      }

      render(<ConversationMessageComponent message={agentMessage} />)

      // Message should render (timestamps are not displayed in the current implementation)
      expect(screen.getByText('Test message')).toBeInTheDocument()
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

      // Check the approval header contains the warning icon and text
      const awaitingText = screen.getByText(/Awaiting Approval/i)
      expect(awaitingText).toBeInTheDocument()

      // Check for warning icon (SVG) - it's a sibling of the text, in the header div
      const headerDiv = awaitingText.closest('div')
      const svg = headerDiv?.querySelector('svg')
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

      // Text is split across elements, so use title attribute which contains full text
      expect(screen.getByTitle('Awaiting Approval: create_new_task')).toBeInTheDocument()
      // Also verify the individual parts are rendered
      expect(screen.getByText(/Awaiting Approval/i)).toBeInTheDocument()
      expect(screen.getByText('create_new_task')).toBeInTheDocument()
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

      // Check for proper container structure - outer flex container
      const outerContainer = container.querySelector('.flex.w-full')
      expect(outerContainer).toBeTruthy()

      // Check for the card container with rounded styling
      const card = container.querySelector('.rounded-md')
      expect(card).toBeTruthy()
    })
  })

  describe('system events', () => {
    it('renders workspace_create event as inline badge', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'workspace_create',
        data: { task_id: 123 },
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={systemEvent} />)

      // Check for centered container
      const container = screen.getByText('Creating workspace').closest('.justify-center')
      expect(container).toBeInTheDocument()

      // Check for badge styling
      const badge = screen.getByText('Creating workspace').closest('.rounded-full')
      expect(badge).toBeInTheDocument()
      expect(badge).toHaveClass('bg-blue-500/10', 'border-blue-500/20', 'text-blue-400')

      // Check for info icon
      const svg = badge?.querySelector('svg')
      expect(svg).toBeInTheDocument()
    })

    it('renders workspace_allocate event as system badge', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'workspace_allocate',
        data: { task_id: 123, slot_id: 1 },
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={systemEvent} />)

      expect(screen.getByText('Allocating workspace')).toBeInTheDocument()
      const badge = screen.getByText('Allocating workspace').closest('.rounded-full')
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400')
    })

    it('renders workspace_branch_checkout event as system badge', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'workspace_branch_checkout',
        data: { task_id: 123, branch: 'main' },
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={systemEvent} />)

      expect(screen.getByText('Checking out branch')).toBeInTheDocument()
      const badge = screen.getByText('Checking out branch').closest('.rounded-full')
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400')
    })

    it('renders workspace_setup event as system badge', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'workspace_setup',
        data: { task_id: 123, codebase_id: 1, setup_command: 'npm install' },
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={systemEvent} />)

      expect(screen.getByText('Running workspace setup')).toBeInTheDocument()
      const badge = screen.getByText('Running workspace setup').closest('.rounded-full')
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400')
    })

    it('does not render task_updated event (hidden)', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'task_updated',
        data: { task_id: 123, updated_fields: { status: 'planning' } },
        timestamp: '2024-01-01T10:00:00Z',
      }

      const { container } = render(<ConversationMessageComponent message={systemEvent} />)

      // Should render nothing
      expect(container.firstChild).toBeNull()
    })

    it('does not render conversation_updated event (hidden)', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'conversation_updated',
        data: { conversation_id: 456, updated_fields: { external_session_id: 'abc123' } },
        timestamp: '2024-01-01T10:00:00Z',
      }

      const { container } = render(<ConversationMessageComponent message={systemEvent} />)

      // Should render nothing
      expect(container.firstChild).toBeNull()
    })

    it('renders branch_rebased event with message from data', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'branch_rebased',
        data: { task_id: 123, message: 'Rebased onto main', new_head: 'abc123' },
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={systemEvent} />)

      expect(screen.getByText('Rebased onto main')).toBeInTheDocument()
      const badge = screen.getByText('Rebased onto main').closest('.rounded-full')
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400')
    })

    it('renders stash_apply_conflict event as system badge', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'stash_apply_conflict',
        data: { task_id: 123, message: 'Stash apply had conflicts', conflicted_files: ['file.ts'] },
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={systemEvent} />)

      expect(screen.getByText('Stash apply conflict - agent resolving')).toBeInTheDocument()
      const badge = screen.getByText('Stash apply conflict - agent resolving').closest('.rounded-full')
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400')
    })

    it('renders compacting_conversation event as system badge', () => {
      const systemEvent: SystemEvent = {
        event_type: 'system',
        type: 'compacting_conversation',
        data: null,
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={systemEvent} />)

      expect(screen.getByText('Compacting conversation...')).toBeInTheDocument()
      const badge = screen.getByText('Compacting conversation...').closest('.rounded-full')
      expect(badge).toHaveClass('bg-blue-500/10', 'text-blue-400')
    })

    it('does not render unknown system event types', () => {
      const systemEvent = {
        event_type: 'system',
        type: 'unknown_system_event',
        data: null,
        timestamp: '2024-01-01T10:00:00Z',
      } as unknown as SystemEvent

      const { container } = render(<ConversationMessageComponent message={systemEvent} />)

      // Should render nothing
      expect(container.firstChild).toBeNull()
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

  describe('thinking events', () => {
    it('renders thinking event with duration derived from previousEventTimestamp', () => {
      const thinkingEvent: ThinkingEvent = {
        event_type: 'thinking',

        thinking_text: null,
        timestamp: '2024-01-01T10:00:04.100Z',
      }

      render(<ConversationMessageComponent message={thinkingEvent} previousEventTimestamp="2024-01-01T10:00:00Z" />)

      const span = screen.getByText('Thought for 4.1s')
      expect(span).toBeInTheDocument()
      expect(span).toHaveClass('italic')
      expect(span).toHaveClass('text-gray-500')
    })

    it('renders thinking event without previousEventTimestamp showing just "Thought"', () => {
      const thinkingEvent: ThinkingEvent = {
        event_type: 'thinking',

        thinking_text: null,
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={thinkingEvent} />)

      expect(screen.getByText('Thought')).toBeInTheDocument()
    })

    it('does not render purple pill or centered layout', () => {
      const thinkingEvent: ThinkingEvent = {
        event_type: 'thinking',

        thinking_text: null,
        timestamp: '2024-01-01T10:00:00Z',
      }

      render(<ConversationMessageComponent message={thinkingEvent} />)

      expect(screen.queryByText(/Thinking/)).not.toBeInTheDocument()
      expect(document.querySelector('.justify-center')).not.toBeInTheDocument()
      expect(document.querySelector('.rounded-full')).not.toBeInTheDocument()
      expect(document.querySelector('.bg-purple-500\\/10')).not.toBeInTheDocument()
    })

    it('shows expand toggle and reveals thinking text on click', async () => {
      const thinkingEvent: ThinkingEvent = {
        event_type: 'thinking',

        thinking_text: 'Let me think about this carefully.',
        timestamp: '2024-01-01T10:00:03.000Z',
      }

      render(<ConversationMessageComponent message={thinkingEvent} previousEventTimestamp="2024-01-01T10:00:00Z" />)

      expect(screen.queryByText('Let me think about this carefully.')).not.toBeInTheDocument()

      const button = screen.getByRole('button')
      expect(button).toHaveTextContent('Thought for 3.0s')

      await userEvent.click(button)
      expect(screen.getByText('Let me think about this carefully.')).toBeInTheDocument()

      await userEvent.click(button)
      expect(screen.queryByText('Let me think about this carefully.')).not.toBeInTheDocument()
    })
  })

  describe('model name in tooltip', () => {
    it('shows model name in agent message tooltip when model is provided', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'Response text',
        timestamp: '2024-01-01T10:00:10Z',
        model: 'claude-sonnet-4-20250514',
      }

      const { container } = render(
        <ConversationMessageComponent
          message={agentMessage}
          previousEventTimestamp="2024-01-01T10:00:00Z"
        />
      )

      const timingEl = container.querySelector('.opacity-0.group-hover\\:opacity-100')
      expect(timingEl).toBeInTheDocument()
      expect(timingEl?.textContent).toContain('claude-sonnet-4-20250514')
      expect(timingEl?.textContent).toContain('·')
    })

    it('does not show model separator in agent message tooltip when model is not provided', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'Response text',
        timestamp: '2024-01-01T10:00:10Z',
      }

      const { container } = render(
        <ConversationMessageComponent
          message={agentMessage}
          previousEventTimestamp="2024-01-01T10:00:00Z"
        />
      )

      const timingEl = container.querySelector('.opacity-0.group-hover\\:opacity-100')
      expect(timingEl).toBeInTheDocument()
      expect(timingEl?.textContent).not.toContain('·')
    })
  })

  describe('hover-reveal timestamps', () => {
    it('user message has group class for hover and timing badge', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Hello',
        timestamp: '2024-01-01T10:00:05Z',
      }

      const { container } = render(
        <ConversationMessageComponent
          message={userMessage}
          previousEventTimestamp="2024-01-01T10:00:00Z"
        />
      )

      // Outer container has group class
      const groupEl = container.querySelector('.group')
      expect(groupEl).toBeInTheDocument()

      // Timing badge exists and is initially hidden
      const timingEl = container.querySelector('.opacity-0.group-hover\\:opacity-100')
      expect(timingEl).toBeInTheDocument()
      // Should contain delay text (5s) — format is "HH:MM:SS (5.0s)"
      expect(timingEl?.textContent).toContain('5.0s')
    })

    it('agent message has group class and timing badge', () => {
      const agentMessage: ConversationMessage = {
        event_type: 'message',
        role: 'agent',
        text_content: 'Response text',
        timestamp: '2024-01-01T10:00:10Z',
      }

      const { container } = render(
        <ConversationMessageComponent
          message={agentMessage}
          previousEventTimestamp="2024-01-01T10:00:00Z"
        />
      )

      const groupEl = container.querySelector('.group')
      expect(groupEl).toBeInTheDocument()

      const timingEl = container.querySelector('.opacity-0.group-hover\\:opacity-100')
      expect(timingEl).toBeInTheDocument()
      expect(timingEl?.textContent).toContain('10.0s')
    })

    it('user message without previousEventTimestamp shows only HH:MM', () => {
      const userMessage: ConversationMessage = {
        event_type: 'message',
        role: 'user',
        text_content: 'Hello',
        timestamp: '2024-01-01T10:05:00Z',
      }

      const { container } = render(<ConversationMessageComponent message={userMessage} />)

      const timingEl = container.querySelector('.opacity-0.group-hover\\:opacity-100')
      expect(timingEl).toBeInTheDocument()
      // Should not contain a delay component
      expect(timingEl?.textContent).not.toContain('+')
    })
  })
})
