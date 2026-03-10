import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '../../../test/utils'
import ConversationMessageList from '../ConversationMessageList'
import type { ConversationEvent, ToolCall, ToolResult } from '../../../lib/api'

vi.mock('../ConversationMessage', () => ({
  default: ({ message }: { message: ConversationEvent }) => (
    <div
      data-testid="conversation-message"
      data-event-type={message.event_type}
      data-role={(message as { role?: string }).role}
    />
  ),
}))

vi.mock('../ToolCallDisplay', () => ({
  default: ({ toolCall }: { toolCall: ToolCall }) => (
    <div data-testid="tool-call-display" data-tool-name={toolCall.tool_name} />
  ),
}))

vi.mock('../ToolCallGroupDisplay', () => ({
  default: ({ items }: { items: Array<{ message: ToolCall; index: number }> }) => (
    <div data-testid="tool-call-group-display" data-count={items.length} />
  ),
}))

vi.mock('../PendingMessage', () => ({
  default: () => <div data-testid="pending-message" />,
}))

function makeMessage(id: string): ConversationEvent {
  return {
    event_type: 'message',
    role: 'agent',
    text_content: `Message ${id}`,
    timestamp: `2024-01-01T10:00:${id}Z`,
  }
}

function makeUserMessage(id: string): ConversationEvent {
  return {
    event_type: 'message',
    role: 'user',
    text_content: `User message ${id}`,
    timestamp: `2024-01-01T10:00:${id}Z`,
  }
}

function makeToolCall(id: string): ToolCall {
  return {
    event_type: 'tool_call',
    tool_call_id: `call_${id}`,
    tool_name: 'Read',
    tool_args: null,
    timestamp: `2024-01-01T10:00:${id}Z`,
  }
}

function makeToolResult(toolCallId: string, id: string): ToolResult {
  return {
    event_type: 'tool_result',
    tool_call_id: toolCallId,
    result_content: 'result',
    is_error: false,
    timestamp: `2024-01-01T10:01:${id}Z`,
  }
}

const defaultProps = {
  pendingMessage: null,
  onRetryMessage: vi.fn(),
  emptyStateMessage: 'No messages',
  showEmptyState: false,
}

describe('ConversationMessageList', () => {
  describe('No grouping', () => {
    it('renders a single tool call between messages without grouping', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeToolCall('02'),
        makeMessage('03'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // All 3 events rendered as individual conversation-message elements (message + tool_call + message)
      expect(screen.getAllByTestId('conversation-message')).toHaveLength(3)
      expect(screen.queryByTestId('tool-call-group-display')).not.toBeInTheDocument()
    })
  })

  describe('Grouping', () => {
    it('groups 3 consecutive tool calls followed by a message into one ToolCallGroupDisplay', () => {
      const messages: ConversationEvent[] = [
        makeToolCall('01'),
        makeToolCall('02'),
        makeToolCall('03'),
        makeMessage('04'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const group = screen.getByTestId('tool-call-group-display')
      expect(group).toBeInTheDocument()
      expect(group).toHaveAttribute('data-count', '3')
      expect(screen.queryByTestId('tool-call-display')).not.toBeInTheDocument()
    })

    it('groups 2 consecutive tool calls into a ToolCallGroupDisplay', () => {
      const messages: ConversationEvent[] = [
        makeToolCall('01'),
        makeToolCall('02'),
        makeMessage('03'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      expect(screen.getByTestId('tool-call-group-display')).toBeInTheDocument()
      expect(screen.queryByTestId('tool-call-display')).not.toBeInTheDocument()
    })
  })

  describe('Trailing exception', () => {
    it('does not group trailing tool calls at end of messages list', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeToolCall('02'),
        makeToolCall('03'),
        makeToolCall('04'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // All 4 events rendered individually (no grouping for trailing tool calls)
      expect(screen.queryByTestId('tool-call-group-display')).not.toBeInTheDocument()
      expect(screen.getAllByTestId('conversation-message')).toHaveLength(4)
    })

    it('renders a single trailing tool call as individual display', () => {
      const messages: ConversationEvent[] = [makeMessage('01'), makeToolCall('02')]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      expect(screen.queryByTestId('tool-call-group-display')).not.toBeInTheDocument()
      expect(screen.getAllByTestId('conversation-message')).toHaveLength(2)
    })
  })

  describe('Group breaking', () => {
    it('tool calls separated by a message event form two separate groups', () => {
      const messages: ConversationEvent[] = [
        makeToolCall('01'),
        makeToolCall('02'),
        makeMessage('03'),
        makeToolCall('04'),
        makeToolCall('05'),
        makeMessage('06'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      expect(screen.getAllByTestId('tool-call-group-display')).toHaveLength(2)
    })

    it('tool_result events between tool_call events do not break the group', () => {
      const tc01 = makeToolCall('01')
      const tc02 = makeToolCall('02')
      const messages: ConversationEvent[] = [
        tc01,
        makeToolResult(tc01.tool_call_id, '01b'),
        tc02,
        makeToolResult(tc02.tool_call_id, '02b'),
        makeMessage('03'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      expect(screen.getByTestId('tool-call-group-display')).toBeInTheDocument()
      expect(screen.queryByTestId('tool-call-display')).not.toBeInTheDocument()
    })
  })

  describe('Mixed sequences', () => {
    it('handles complex sequence: message, group, single tool call, message, trailing tools', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeToolCall('02'),
        makeToolCall('03'),
        makeMessage('04'),
        makeToolCall('05'),
        makeMessage('06'),
        makeToolCall('07'),
        makeToolCall('08'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // One group (02, 03 before message 04)
      expect(screen.getByTestId('tool-call-group-display')).toBeInTheDocument()
      // Three messages (01, 04, 06) + one single tool call (05) + two trailing tool calls (07, 08)
      // = 6 conversation-message elements
      expect(screen.getAllByTestId('conversation-message')).toHaveLength(6)
    })
  })

  describe('Agent block grouping', () => {
    it('wraps consecutive agent messages and tool calls in a single agent block', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeToolCall('02'),
        makeMessage('03'),
      ]

      const { container } = render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // All non-user items grouped into one agent block div
      const agentBlocks = container.querySelectorAll('.flex.flex-col')
      expect(agentBlocks).toHaveLength(1)
    })

    it('user messages break agent blocks', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeUserMessage('02'),
        makeMessage('03'),
      ]

      const { container } = render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // Two separate agent blocks (before and after the user message)
      const agentBlocks = container.querySelectorAll('.flex.flex-col')
      expect(agentBlocks).toHaveLength(2)
    })

    it('renders user messages as direct siblings of agent blocks (not inside them)', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeUserMessage('02'),
        makeMessage('03'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const userMessages = document.querySelectorAll('[data-role="user"]')
      expect(userMessages).toHaveLength(1)
      // User message should not be inside an agent block div
      expect(userMessages[0].closest('.flex.flex-col')).toBeNull()
    })

    it('groups multiple turns correctly', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeToolCall('02'),
        makeUserMessage('03'),
        makeMessage('04'),
        makeUserMessage('05'),
        makeMessage('06'),
      ]

      const { container } = render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // Three agent blocks: [msg01+tc02], [msg04], [msg06]
      const agentBlocks = container.querySelectorAll('.flex.flex-col')
      expect(agentBlocks).toHaveLength(3)

      const userMessages = document.querySelectorAll('[data-role="user"]')
      expect(userMessages).toHaveLength(2)
    })

    it('handles conversation starting with a user message', () => {
      const messages: ConversationEvent[] = [
        makeUserMessage('01'),
        makeMessage('02'),
      ]

      const { container } = render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const agentBlocks = container.querySelectorAll('.flex.flex-col')
      expect(agentBlocks).toHaveLength(1)

      const userMessages = document.querySelectorAll('[data-role="user"]')
      expect(userMessages).toHaveLength(1)
    })
  })

  describe('Empty state', () => {
    it('renders empty state message when showEmptyState is true', () => {
      render(
        <ConversationMessageList
          messages={[]}
          {...defaultProps}
          showEmptyState={true}
          emptyStateMessage="Start a conversation"
        />
      )

      expect(screen.getByText('Start a conversation')).toBeInTheDocument()
    })
  })
})
