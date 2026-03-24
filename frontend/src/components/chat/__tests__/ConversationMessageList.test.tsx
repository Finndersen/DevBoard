import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '../../../test/utils'
import ConversationMessageList from '../ConversationMessageList'
import type { ConversationEvent, ThinkingEvent, ToolCall, ToolResult } from '../../../lib/api'

vi.mock('../ConversationMessage', () => ({
  default: ({ message, previousEventTimestamp }: { message: ConversationEvent; previousEventTimestamp?: string | null }) => (
    <div
      data-testid="conversation-message"
      data-event-type={message.event_type}
      data-role={(message as { role?: string }).role}
      data-prev-ts={previousEventTimestamp ?? ''}
    />
  ),
}))

vi.mock('../ToolCallDisplay', () => ({
  default: ({ toolCall }: { toolCall: ToolCall }) => (
    <div data-testid="tool-call-display" data-tool-name={toolCall.tool_name} />
  ),
}))

vi.mock('../ToolCallGroupDisplay', () => ({
  default: ({ items }: { items: Array<{ message: ToolCall; index: number; previousEventTimestamp?: string | null }> }) => (
    <div data-testid="tool-call-group-display" data-count={items.length} data-prev-ts={items[0]?.previousEventTimestamp ?? ''} />
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

function makeThinkingEvent(id: string): ThinkingEvent {
  return {
    event_type: 'thinking',
    timestamp: `2024-01-01T10:00:${id}Z`,
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

  describe('ThinkingEvent', () => {
    it('renders a ThinkingEvent as a conversation-message element', () => {
      const messages: ConversationEvent[] = [
        makeThinkingEvent('01'),
        makeMessage('02'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const els = screen.getAllByTestId('conversation-message')
      expect(els).toHaveLength(2)
      expect(els[0]).toHaveAttribute('data-event-type', 'thinking')
    })

    it('ThinkingEvent between tool calls breaks tool call grouping', () => {
      const messages: ConversationEvent[] = [
        makeToolCall('01'),
        makeToolCall('02'),
        makeThinkingEvent('03'),
        makeToolCall('04'),
        makeToolCall('05'),
        makeMessage('06'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // ThinkingEvent breaks the group: first two tool calls form one group,
      // thinking is a single item, last two tool calls form a second group
      expect(screen.getAllByTestId('tool-call-group-display')).toHaveLength(2)
      const conversationMessages = screen.getAllByTestId('conversation-message')
      const thinkingEl = conversationMessages.find(el => el.getAttribute('data-event-type') === 'thinking')
      expect(thinkingEl).toBeDefined()
    })

    it('ThinkingEvent is part of agent blocks (not treated as user message)', () => {
      const messages: ConversationEvent[] = [
        makeUserMessage('01'),
        makeThinkingEvent('02'),
        makeMessage('03'),
      ]

      const { container } = render(<ConversationMessageList messages={messages} {...defaultProps} />)

      // One agent block containing the thinking event and agent message
      const agentBlocks = container.querySelectorAll('.flex.flex-col')
      expect(agentBlocks).toHaveLength(1)
    })
  })

  describe('previousEventTimestamp threading', () => {
    it('first event has null previousEventTimestamp', () => {
      const messages: ConversationEvent[] = [makeMessage('01')]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const el = screen.getByTestId('conversation-message')
      expect(el.getAttribute('data-prev-ts')).toBe('')
    })

    it('second event gets the first event timestamp as previousEventTimestamp', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeMessage('02'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const els = screen.getAllByTestId('conversation-message')
      expect(els[1].getAttribute('data-prev-ts')).toBe('2024-01-01T10:00:01Z')
    })

    it('tool call group gets the timestamp of the event before the group', () => {
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        makeToolCall('02'),
        makeToolCall('03'),
        makeMessage('04'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const group = screen.getByTestId('tool-call-group-display')
      expect(group.getAttribute('data-prev-ts')).toBe('2024-01-01T10:00:01Z')
    })

    it('tool_result events are skipped when computing previousEventTimestamp', () => {
      const tc = makeToolCall('02')
      const messages: ConversationEvent[] = [
        makeMessage('01'),
        tc,
        makeToolResult(tc.tool_call_id, '03'),
        makeMessage('04'),
      ]

      render(<ConversationMessageList messages={messages} {...defaultProps} />)

      const els = screen.getAllByTestId('conversation-message')
      // Last message (04) previous should be the tool_call at 02, not the tool_result at 03
      expect(els[els.length - 1].getAttribute('data-prev-ts')).toBe('2024-01-01T10:00:02Z')
    })
  })
})
