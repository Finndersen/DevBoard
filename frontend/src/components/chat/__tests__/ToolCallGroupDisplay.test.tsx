import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import ToolCallGroupDisplay from '../ToolCallGroupDisplay'
import type { ToolCall, ToolResult } from '../../../lib/api'

vi.mock('../ToolCallDisplay', () => ({
  default: ({ toolCall, isHighlighted }: { toolCall: ToolCall; toolResult?: ToolResult; isHighlighted?: boolean }) => (
    <div data-testid="tool-call-display">
      <span data-testid="tool-name">{toolCall.tool_name}</span>
      {isHighlighted && <span data-testid="highlighted">highlighted</span>}
    </div>
  ),
}))

function makeToolCall(toolName: string, index: number, uuid?: string): { message: ToolCall; index: number } {
  return {
    message: {
      event_type: 'tool_call',
      tool_call_id: `call_${index}`,
      tool_name: toolName,
      tool_args: null,
      timestamp: `2024-01-01T10:00:0${index}Z`,
      uuid,
    },
    index,
  }
}

function makeToolResult(toolCall: ToolCall, index: number, isError = false): [string, ToolResult] {
  const cacheKey = `${toolCall.timestamp}-tool_call-${index}`
  const result: ToolResult = {
    event_type: 'tool_result',
    tool_call_id: toolCall.tool_call_id,
    result_content: isError ? 'Error occurred' : 'Success',
    is_error: isError,
    timestamp: `2024-01-01T10:00:1${index}Z`,
  }
  return [cacheKey, result]
}

describe('ToolCallGroupDisplay', () => {
  describe('Collapsed state', () => {
    it('renders summary heading with correct tool name counts', () => {
      const items = [
        makeToolCall('Read', 0),
        makeToolCall('Read', 1),
        makeToolCall('Read', 2),
        makeToolCall('Bash', 3),
        makeToolCall('Bash', 4),
      ]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      expect(screen.getByText('Read (3), Bash (2)')).toBeInTheDocument()
    })

    it('renders single-occurrence tools without count parentheses', () => {
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      expect(screen.getByText('Read, Bash')).toBeInTheDocument()
    })

    it('shows count badge with total number of tool calls', () => {
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1), makeToolCall('Edit', 2)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      expect(screen.getByText('3 tool calls')).toBeInTheDocument()
    })

    it('does not show individual tool calls when collapsed', () => {
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      expect(screen.queryAllByTestId('tool-call-display')).toHaveLength(0)
    })
  })

  describe('Status indicators', () => {
    it('shows spinner (running) when any tool has no result', () => {
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]
      const toolResultMap = new Map<string, ToolResult>()
      const [key, result] = makeToolResult(items[0].message, 0)
      toolResultMap.set(key, result)
      // items[1] has no result

      const { container } = render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={toolResultMap}
          highlightSet={new Set()}
        />
      )

      expect(container.querySelector('.animate-spin')).toBeInTheDocument()
    })

    it('shows green checkmark when all tools completed successfully', () => {
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]
      const toolResultMap = new Map<string, ToolResult>()
      const [key0, result0] = makeToolResult(items[0].message, 0)
      const [key1, result1] = makeToolResult(items[1].message, 1)
      toolResultMap.set(key0, result0)
      toolResultMap.set(key1, result1)

      const { container } = render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={toolResultMap}
          highlightSet={new Set()}
        />
      )

      expect(container.querySelector('.text-green-600, .text-green-400')).toBeInTheDocument()
      expect(container.querySelector('.animate-spin')).not.toBeInTheDocument()
    })

    it('shows red X when any tool has an error result', () => {
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]
      const toolResultMap = new Map<string, ToolResult>()
      const [key0, result0] = makeToolResult(items[0].message, 0)
      const [key1, result1] = makeToolResult(items[1].message, 1, true)
      toolResultMap.set(key0, result0)
      toolResultMap.set(key1, result1)

      const { container } = render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={toolResultMap}
          highlightSet={new Set()}
        />
      )

      expect(container.querySelector('.text-red-600, .text-red-400')).toBeInTheDocument()
    })
  })

  describe('Expand/collapse', () => {
    it('expands to show individual tool calls when clicked', async () => {
      const user = userEvent.setup()
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      expect(screen.queryAllByTestId('tool-call-display')).toHaveLength(0)

      await user.click(screen.getByRole('button'))

      expect(screen.getAllByTestId('tool-call-display')).toHaveLength(2)
    })

    it('collapses back when clicked again', async () => {
      const user = userEvent.setup()
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      await user.click(screen.getByRole('button'))
      expect(screen.getAllByTestId('tool-call-display')).toHaveLength(2)

      await user.click(screen.getByRole('button'))
      expect(screen.queryAllByTestId('tool-call-display')).toHaveLength(0)
    })

    it('renders all individual tool calls when expanded', async () => {
      const user = userEvent.setup()
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1), makeToolCall('Edit', 2)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      await user.click(screen.getByRole('button'))

      expect(screen.getAllByTestId('tool-call-display')).toHaveLength(3)
      expect(screen.getByText('Read')).toBeInTheDocument()
      expect(screen.getByText('Bash')).toBeInTheDocument()
      expect(screen.getByText('Edit')).toBeInTheDocument()
    })
  })

  describe('Highlight behaviour', () => {
    it('auto-expands when a tool call uuid matches the highlight set', () => {
      const items = [makeToolCall('Read', 0, 'uuid-abc'), makeToolCall('Bash', 1)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set(['uuid-abc'])}
        />
      )

      // Should already be expanded
      expect(screen.getAllByTestId('tool-call-display')).toHaveLength(2)
    })

    it('does not auto-expand when no highlight matches', () => {
      const items = [makeToolCall('Read', 0, 'uuid-abc'), makeToolCall('Bash', 1)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set(['uuid-other'])}
        />
      )

      expect(screen.queryAllByTestId('tool-call-display')).toHaveLength(0)
    })

    it('applies amber highlight ring when any item is highlighted', () => {
      const items = [makeToolCall('Read', 0, 'uuid-abc'), makeToolCall('Bash', 1)]

      const { container } = render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set(['uuid-abc'])}
        />
      )

      expect(container.querySelector('.ring-2.ring-amber-400, .ring-2.ring-amber-500')).toBeInTheDocument()
    })

    it('does not apply highlight ring when no items are highlighted', () => {
      const items = [makeToolCall('Read', 0), makeToolCall('Bash', 1)]

      const { container } = render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      expect(container.querySelector('.ring-2')).not.toBeInTheDocument()
    })
  })

  describe('MCP tool name cleaning', () => {
    it('strips mcp__ prefix from tool names in summary', () => {
      const items = [makeToolCall('mcp__github__get_repo', 0), makeToolCall('mcp__github__get_repo', 1)]

      render(
        <ToolCallGroupDisplay
          items={items}
          toolResultMap={new Map()}
          highlightSet={new Set()}
        />
      )

      expect(screen.getByText('github__get_repo (2)')).toBeInTheDocument()
    })
  })
})
