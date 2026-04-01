import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render, mockNavigate } from '../../../test/utils'
import ToolCallDisplay from '../ToolCallDisplay'
import type { ToolCall, ToolResult } from '../../../lib/api'

vi.mock('../../../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api')
  return {
    ...actual,
    apiClient: {
      getClaudeCodeSubAgentMessages: vi.fn().mockResolvedValue([]),
      getConversationMessages: vi.fn().mockResolvedValue([]),
    },
  }
})

vi.mock('../../claude-code/SubAgentConversationModal', () => ({
  default: ({ isOpen, title, subagentType, subtitle }: { isOpen: boolean; onClose: () => void; fetchMessages: () => Promise<unknown[]>; title: string; subagentType?: string; subtitle?: string }) => (
    isOpen ? <div data-testid="sub-agent-modal" data-subagent-type={subagentType} data-subtitle={subtitle}>{title}</div> : null
  ),
}))

describe('ToolCallDisplay', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
  })

  const mockToolCall: ToolCall = {
    event_type: 'tool_call',
    tool_call_id: 'call_123',
    tool_name: 'search_codebase',
    tool_args: {
      query: 'test search',
      max_results: 10,
    },
    timestamp: '2024-01-01T10:00:00Z',
  }

  const mockToolResult: ToolResult = {
    event_type: 'tool_result',
    tool_call_id: 'call_123',
    result_content: 'Found 5 results matching your query',
    is_error: false,
    timestamp: '2024-01-01T10:00:05Z',
  }

  const mockErrorResult: ToolResult = {
    event_type: 'tool_result',
    tool_call_id: 'call_123',
    result_content: 'Error: Connection timeout',
    is_error: true,
    timestamp: '2024-01-01T10:00:05Z',
  }

  describe('Collapsed State', () => {
    it('renders in collapsed state by default', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Should show tool name
      expect(screen.getByText('search_codebase')).toBeInTheDocument()

      // Should NOT show arguments when collapsed
      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
      expect(screen.queryByText(/"query": "test search"/)).not.toBeInTheDocument()
    })

    it('renders button with correct role', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toBeInTheDocument()
    })

    it('shows running status icon when no result', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Should show "Running..." text
      expect(screen.getByText('Running...')).toBeInTheDocument()

      // Should show spinning icon with theme-aware classes
      const spinner = container.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
      expect(spinner).toHaveClass('text-blue-600', 'dark:text-blue-400')
    })

    it('shows complete status icon when result exists', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      // Should show green checkmark icon with theme-aware classes
      const checkmark = container.querySelector('.text-green-600')
      expect(checkmark).toBeInTheDocument()
      expect(checkmark).toHaveClass('dark:text-green-400')

      // Should NOT show "Running..." text
      expect(screen.queryByText('Running...')).not.toBeInTheDocument()
    })

    it('shows error status icon when error result exists', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockErrorResult} />)

      // Should show red X icon with theme-aware classes
      const errorIcon = container.querySelector('.text-red-600')
      expect(errorIcon).toBeInTheDocument()
      expect(errorIcon).toHaveClass('dark:text-red-400')

      // Should NOT show "Running..." text
      expect(screen.queryByText('Running...')).not.toBeInTheDocument()
    })

    it('shows chevron down icon when collapsed', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Find chevron (should not be rotated)
      // The chevron SVG is the last svg element in the button
      const svgs = container.querySelectorAll('svg')
      const chevron = svgs[svgs.length - 1]
      expect(chevron).toBeInTheDocument()
      expect(chevron).not.toHaveClass('rotate-180')
    })

    it('uses neutral hover styling regardless of state', () => {
      const { rerender } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('rounded-md', 'overflow-hidden')

      rerender(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)
      expect(button).toHaveClass('rounded-md', 'overflow-hidden')

      rerender(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockErrorResult} />)
      expect(button).toHaveClass('rounded-md', 'overflow-hidden')
    })
  })

  describe('Expansion Behavior', () => {
    it('expands to show details when clicked', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Should NOT see arguments initially
      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()

      // Click to expand
      await user.click(screen.getByRole('button'))

      // Now should see arguments
      expect(screen.getByText('Arguments:')).toBeInTheDocument()
      expect(screen.getByText(/"query": "test search"/)).toBeInTheDocument()
    })

    it('collapses when clicked again', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Expand
      await user.click(screen.getByRole('button'))
      expect(screen.getByText('Arguments:')).toBeInTheDocument()

      // Collapse
      await user.click(screen.getByRole('button'))
      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
    })

    it('rotates chevron when expanded', async () => {
      const user = userEvent.setup()
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Click to expand
      await user.click(screen.getByRole('button'))

      // Find chevron (should be rotated)
      const chevron = container.querySelector('.rotate-180')
      expect(chevron).toBeInTheDocument()
    })

    it('rotates chevron back when collapsed', async () => {
      const user = userEvent.setup()
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Expand
      await user.click(screen.getByRole('button'))
      expect(container.querySelector('.rotate-180')).toBeInTheDocument()

      // Collapse
      await user.click(screen.getByRole('button'))
      expect(container.querySelector('.rotate-180')).not.toBeInTheDocument()
    })
  })

  describe('Expanded State - Arguments', () => {
    it('renders tool call with arguments when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('search_codebase')).toBeInTheDocument()
      expect(screen.getByText(/Arguments:/)).toBeInTheDocument()
      expect(screen.getByText(/"query": "test search"/)).toBeInTheDocument()
      expect(screen.getByText(/"max_results": 10/)).toBeInTheDocument()
    })

    it('does not render arguments section when args is null', async () => {
      const user = userEvent.setup()
      const toolCallWithoutArgs: ToolCall = {
        ...mockToolCall,
        tool_args: null,
      }

      render(<ToolCallDisplay toolCall={toolCallWithoutArgs} />)
      await user.click(screen.getByRole('button'))

      expect(screen.getByText('search_codebase')).toBeInTheDocument()
      expect(screen.queryByText(/Arguments:/)).not.toBeInTheDocument()
    })

    it('does not render arguments section when args is empty object', async () => {
      const user = userEvent.setup()
      const toolCallWithEmptyArgs: ToolCall = {
        ...mockToolCall,
        tool_args: {},
      }

      render(<ToolCallDisplay toolCall={toolCallWithEmptyArgs} />)
      await user.click(screen.getByRole('button'))

      expect(screen.getByText('search_codebase')).toBeInTheDocument()
      expect(screen.queryByText(/Arguments:/)).not.toBeInTheDocument()
    })

    it('displays formatted JSON arguments correctly when expanded', async () => {
      const user = userEvent.setup()
      const complexArgs: ToolCall = {
        ...mockToolCall,
        tool_args: {
          filters: {
            type: 'code',
            language: 'typescript',
          },
          options: {
            case_sensitive: true,
            regex: false,
          },
        },
      }

      render(<ToolCallDisplay toolCall={complexArgs} />)
      await user.click(screen.getByRole('button'))

      // Check for formatted JSON with proper indentation
      expect(screen.getByText(/"filters":/)).toBeInTheDocument()
      expect(screen.getByText(/"type": "code"/)).toBeInTheDocument()
      expect(screen.getByText(/"language": "typescript"/)).toBeInTheDocument()
      expect(screen.getByText(/"case_sensitive": true/)).toBeInTheDocument()
    })

    it('displays tool call with special characters in arguments when expanded', async () => {
      const user = userEvent.setup()
      const specialCharsToolCall: ToolCall = {
        ...mockToolCall,
        tool_args: {
          pattern: '.*\\s+test\\s+.*',
          path: '/path/to/file',
          flags: 'gi',
        },
      }

      render(<ToolCallDisplay toolCall={specialCharsToolCall} />)
      await user.click(screen.getByRole('button'))

      // JSON.stringify should escape special characters
      expect(screen.getByText(/"pattern":/)).toBeInTheDocument()
      expect(screen.getByText(/"path": "\/path\/to\/file"/)).toBeInTheDocument()
    })

    it('handles tool call with boolean and number arguments when expanded', async () => {
      const user = userEvent.setup()
      const mixedArgsToolCall: ToolCall = {
        ...mockToolCall,
        tool_args: {
          enabled: true,
          disabled: false,
          count: 42,
          ratio: 3.14,
          nullable: null,
        },
      }

      render(<ToolCallDisplay toolCall={mixedArgsToolCall} />)
      await user.click(screen.getByRole('button'))

      expect(screen.getByText(/"enabled": true/)).toBeInTheDocument()
      expect(screen.getByText(/"disabled": false/)).toBeInTheDocument()
      expect(screen.getByText(/"count": 42/)).toBeInTheDocument()
      expect(screen.getByText(/"ratio": 3.14/)).toBeInTheDocument()
      expect(screen.getByText(/"nullable": null/)).toBeInTheDocument()
    })

    it('handles tool call with nested array arguments when expanded', async () => {
      const user = userEvent.setup()
      const arrayArgsToolCall: ToolCall = {
        ...mockToolCall,
        tool_args: {
          items: ['item1', 'item2', 'item3'],
          nested: [
            { id: 1, name: 'first' },
            { id: 2, name: 'second' },
          ],
        },
      }

      render(<ToolCallDisplay toolCall={arrayArgsToolCall} />)
      await user.click(screen.getByRole('button'))

      expect(screen.getByText(/"items":/)).toBeInTheDocument()
      expect(screen.getByText(/"item1"/)).toBeInTheDocument()
      expect(screen.getByText(/"item2"/)).toBeInTheDocument()
      expect(screen.getByText(/"id": 1/)).toBeInTheDocument()
      expect(screen.getByText(/"name": "first"/)).toBeInTheDocument()
    })

    it('preserves JSON formatting with 2-space indentation when expanded', async () => {
      const user = userEvent.setup()
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      await user.click(screen.getByRole('button'))

      const preElement = container.querySelector('pre')
      expect(preElement).toBeInTheDocument()

      // JSON.stringify with null, 2 should create proper indentation
      const expectedJSON = JSON.stringify(mockToolCall.tool_args, null, 2)
      expect(preElement?.textContent).toBe(expectedJSON)
    })

    it('uses monospace font for arguments when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      await user.click(screen.getByRole('button'))

      // Arguments should use monospace font
      const argsContainer = screen.getByText(/"query": "test search"/).closest('pre')
      expect(argsContainer).toHaveClass('font-mono')
    })
  })

  describe('Expanded State - Results', () => {
    it('renders tool call with successful result when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('search_codebase')).toBeInTheDocument()
      expect(screen.getByText('Result:')).toBeInTheDocument()
      expect(screen.getByText('Found 5 results matching your query')).toBeInTheDocument()
    })

    it('renders tool call with error result when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockErrorResult} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('search_codebase')).toBeInTheDocument()
      expect(screen.getByText('Error:')).toBeInTheDocument()
      expect(screen.getByText('Error: Connection timeout')).toBeInTheDocument()

      // Check for error styling with theme-aware classes
      const errorLabel = screen.getByText('Error:')
      expect(errorLabel).toHaveClass('text-red-700', 'dark:text-red-400')

      const errorContent = screen.getByText('Error: Connection timeout')
      expect(errorContent).toHaveClass('text-red-800', 'dark:text-red-300')
    })

    it('does not render result section when no result', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('search_codebase')).toBeInTheDocument()
      expect(screen.queryByText('Result:')).not.toBeInTheDocument()
      expect(screen.queryByText('Error:')).not.toBeInTheDocument()
    })

    it('applies correct styling for result section with success result', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      const resultLabel = screen.getByText('Result:')
      expect(resultLabel).toHaveClass('text-green-700', 'dark:text-green-400')

      const resultContent = screen.getByText('Found 5 results matching your query')
      expect(resultContent).toHaveClass('text-gray-900', 'dark:text-gray-300')
    })

    it('applies correct styling for result section with error result', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockErrorResult} />)

      await user.click(screen.getByRole('button'))

      const errorLabel = screen.getByText('Error:')
      expect(errorLabel).toHaveClass('text-red-700', 'dark:text-red-400')

      const errorContent = screen.getByText('Error: Connection timeout')
      expect(errorContent).toHaveClass('text-red-800', 'dark:text-red-300')

      // Check for error border styling on the result container with theme-aware classes
      const resultContainer = errorContent.closest('.px-3')
      expect(resultContainer).toHaveClass('border-red-200', 'dark:border-red-800', 'bg-red-50', 'dark:bg-red-900/20')
    })

    it('handles multi-line result content with whitespace preservation', async () => {
      const user = userEvent.setup()
      const multiLineResult: ToolResult = {
        ...mockToolResult,
        result_content: 'Line 1\nLine 2\nLine 3',
      }

      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={multiLineResult} />)
      await user.click(screen.getByRole('button'))

      // Use getByText with a function matcher to find text containing newlines
      const resultContent = screen.getByText((_content, element) => {
        return element?.textContent === 'Line 1\nLine 2\nLine 3'
      })
      expect(resultContent).toHaveClass('whitespace-pre-wrap')
    })

    it('handles empty result content', async () => {
      const user = userEvent.setup()
      const emptyResult: ToolResult = {
        ...mockToolResult,
        result_content: '',
      }

      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={emptyResult} />)
      await user.click(screen.getByRole('button'))

      expect(screen.getByText('Result:')).toBeInTheDocument()
      // Empty content should still render, just with no text
    })

    it('uses monospace font for result content', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      // Result content should use monospace font
      const resultContent = screen.getByText('Found 5 results matching your query')
      expect(resultContent).toHaveClass('font-mono')
    })
  })

  describe('Expanded State - Duration', () => {
    it('displays duration when tool result is present', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      // Duration between 10:00:00 and 10:00:05 should be 5.0s (appears in header and expanded section)
      expect(screen.getAllByText('5.0s').length).toBeGreaterThanOrEqual(1)
    })

    it('displays duration in milliseconds for sub-second durations', async () => {
      const user = userEvent.setup()
      const quickResult: ToolResult = {
        event_type: 'tool_result',
        tool_call_id: 'call_123',
        result_content: 'Quick result',
        is_error: false,
        timestamp: '2024-01-01T10:00:00.234Z',
      }

      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={quickResult} />)

      await user.click(screen.getByRole('button'))

      // Duration should be 234ms (appears in header and expanded section)
      expect(screen.getAllByText('234ms').length).toBeGreaterThanOrEqual(1)
    })

    it('shows duration with correct styling', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      // Check duration styling with theme-aware classes (expanded section element)
      const durations = screen.getAllByText('5.0s')
      const expandedDuration = durations.find(el => el.classList.contains('text-xs'))
      expect(expandedDuration).toBeDefined()
      expect(expandedDuration).toHaveClass('text-xs', 'text-gray-600', 'dark:text-gray-500')
    })
  })

  describe('Layout and Styling', () => {
    it('renders with full width container', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Component uses flex w-full min-w-0 layout
      const wrapper = container.querySelector('.flex.w-full')
      expect(wrapper).toBeTruthy()
    })

    it('has minimum width constraint', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Button has min-w-[300px] class
      const button = container.querySelector('.min-w-\\[300px\\]')
      expect(button).toBeTruthy()
    })

    it('handles very long tool names gracefully', () => {
      const longNameToolCall: ToolCall = {
        ...mockToolCall,
        tool_name: 'very_long_tool_name_that_might_overflow_container_boundaries',
      }

      render(<ToolCallDisplay toolCall={longNameToolCall} />)

      expect(
        screen.getByText('very_long_tool_name_that_might_overflow_container_boundaries')
      ).toBeInTheDocument()
    })

    it('has minimal borderless styling', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('rounded-md', 'overflow-hidden')
      expect(button).not.toHaveClass('border', 'shadow-sm')
    })

    it('applies hover background effect to button', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('transition-colors')
    })
  })

  describe('Edge Cases and Robustness', () => {
    it('handles rapid successive renders without errors', () => {
      const { rerender } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      // Simulate rapid state changes
      rerender(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)
      rerender(<ToolCallDisplay toolCall={mockToolCall} />)
      rerender(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockErrorResult} />)

      expect(screen.getByText('search_codebase')).toBeInTheDocument()
    })

    it('handles rapid expansion/collapse without errors', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')

      // Rapidly click multiple times
      await user.click(button)
      await user.click(button)
      await user.click(button)
      await user.click(button)

      // Should still work correctly
      expect(screen.getByText('search_codebase')).toBeInTheDocument()
    })
  })

  describe('Rich Result Renderers', () => {
    const createTaskToolCall: ToolCall = {
      event_type: 'tool_call',
      tool_call_id: 'call_create_task',
      tool_name: 'create_task',
      tool_args: {
        title: 'New Feature',
        codebase_name: 'backend',
      },
      timestamp: '2024-01-01T10:00:00Z',
    }

    const createTaskResult: ToolResult = {
      event_type: 'tool_result',
      tool_call_id: 'call_create_task',
      result_content: JSON.stringify({
        task_id: 42,
        title: 'New Feature',
        status: 'planning',
        branch_name: 'feature/new-feature',
        base_branch: 'main',
        codebase_name: 'backend',
      }),
      is_error: false,
      timestamp: '2024-01-01T10:00:05Z',
    }

    it('renders create_task result with rich display when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={createTaskToolCall} toolResult={createTaskResult} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('Task created successfully')).toBeInTheDocument()
      expect(screen.getByText('New Feature')).toBeInTheDocument()
      expect(screen.getByText('planning')).toBeInTheDocument()
      expect(screen.getByText('feature/new-feature')).toBeInTheDocument()
      expect(screen.getByText('backend')).toBeInTheDocument()
      expect(screen.getByText('Open Task #42')).toBeInTheDocument()
    })

    it('navigates to task when clicking Open Task button', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={createTaskToolCall} toolResult={createTaskResult} />)

      await user.click(screen.getByRole('button'))
      await user.click(screen.getByText('Open Task #42'))

      expect(mockNavigate).toHaveBeenCalledWith('/tasks/42')
    })

    it('falls back to plain text for create_task with invalid JSON', async () => {
      const user = userEvent.setup()
      const invalidResult: ToolResult = {
        ...createTaskResult,
        result_content: 'Not valid JSON',
      }

      render(<ToolCallDisplay toolCall={createTaskToolCall} toolResult={invalidResult} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('Not valid JSON')).toBeInTheDocument()
      expect(screen.queryByText('Task created successfully')).not.toBeInTheDocument()
    })

    it('falls back to plain text for error results even with valid JSON', async () => {
      const user = userEvent.setup()
      const errorResult: ToolResult = {
        ...createTaskResult,
        is_error: true,
        result_content: JSON.stringify({ error: 'Something went wrong' }),
      }

      render(<ToolCallDisplay toolCall={createTaskToolCall} toolResult={errorResult} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('Error:')).toBeInTheDocument()
      expect(screen.queryByText('Task created successfully')).not.toBeInTheDocument()
    })

    it('renders unknown tools as plain text', async () => {
      const user = userEvent.setup()
      const unknownToolCall: ToolCall = {
        ...createTaskToolCall,
        tool_name: 'unknown_tool',
      }

      const jsonResult: ToolResult = {
        ...createTaskResult,
        result_content: JSON.stringify({ some: 'data' }),
      }

      render(<ToolCallDisplay toolCall={unknownToolCall} toolResult={jsonResult} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('{"some":"data"}')).toBeInTheDocument()
    })
  })

  describe('Sub-Agent Result Renderers', () => {
    const investigateToolCall: ToolCall = {
      event_type: 'tool_call',
      tool_call_id: 'call_investigate',
      tool_name: 'investigate_codebase',
      tool_args: { query: 'How does auth work?' },
      timestamp: '2024-01-01T10:00:00Z',
    }

    const subAgentResult = (toolCall: ToolCall, resultContent: string, isError = false): ToolResult => ({
      event_type: 'tool_result',
      tool_call_id: toolCall.tool_call_id,
      result_content: resultContent,
      is_error: isError,
      timestamp: '2024-01-01T10:00:05Z',
    })

    const validResultContent = JSON.stringify({
      result: '## Summary\n\nThe auth module handles JWT tokens.\n\n- Token validation\n- User lookup',
      conversation_id: 42,
    })

    it('renders investigate_codebase result as markdown when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={investigateToolCall} toolResult={subAgentResult(investigateToolCall, validResultContent)} />)

      await user.click(screen.getAllByRole('button')[0])

      expect(screen.getByRole('heading', { name: 'Summary' })).toBeInTheDocument()
      expect(screen.getByText(/auth module handles JWT tokens/)).toBeInTheDocument()
    })

    it('renders review_code_changes result as markdown when expanded', async () => {
      const user = userEvent.setup()
      const reviewToolCall: ToolCall = {
        ...investigateToolCall,
        tool_call_id: 'call_review',
        tool_name: 'review_code_changes',
      }
      const reviewResult = JSON.stringify({
        result: '## Review\n\nCode looks good.',
        conversation_id: null,
      })

      render(<ToolCallDisplay toolCall={reviewToolCall} toolResult={subAgentResult(reviewToolCall, reviewResult)} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByRole('heading', { name: 'Review' })).toBeInTheDocument()
      expect(screen.getByText('Code looks good.')).toBeInTheDocument()
    })

    it('displays conversation_id when present', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={investigateToolCall} toolResult={subAgentResult(investigateToolCall, validResultContent)} />)

      await user.click(screen.getAllByRole('button')[0])

      expect(screen.getByText('Conversation: 42')).toBeInTheDocument()
    })

    it('does not display conversation_id when null', async () => {
      const user = userEvent.setup()
      const resultWithNullSession = JSON.stringify({
        result: '## Summary\n\nSome result text.',
        conversation_id: null,
      })

      render(<ToolCallDisplay toolCall={investigateToolCall} toolResult={subAgentResult(investigateToolCall, resultWithNullSession)} />)

      await user.click(screen.getByRole('button'))

      expect(screen.queryByText(/^Conversation:/)).not.toBeInTheDocument()
    })

    it('falls back to formatted JSON when result content has invalid shape', async () => {
      const user = userEvent.setup()
      const invalidShapeContent = JSON.stringify({
        result: 123,  // Wrong type - should be string
        conversation_id: 42,
      })

      render(<ToolCallDisplay toolCall={investigateToolCall} toolResult={subAgentResult(investigateToolCall, invalidShapeContent)} />)

      await user.click(screen.getAllByRole('button')[0])

      expect(screen.getByText(/"result": 123/)).toBeInTheDocument()
      expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    })

    it('falls back to plain text when result_content is not valid JSON', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={investigateToolCall} toolResult={subAgentResult(investigateToolCall, 'Not valid JSON')} />)

      await user.click(screen.getByRole('button'))

      expect(screen.getByText('Not valid JSON')).toBeInTheDocument()
      expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    })

    it('falls back to plain text for error results', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={investigateToolCall} toolResult={subAgentResult(investigateToolCall, validResultContent, true)} />)

      await user.click(screen.getAllByRole('button')[0])

      expect(screen.getByText('Error:')).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Summary' })).not.toBeInTheDocument()
    })
  })

  describe('Custom Tool Displays', () => {
    const renderHtmlToolCall: ToolCall = {
      event_type: 'tool_call',
      tool_call_id: 'call_render_html',
      tool_name: 'render_html',
      tool_args: {
        title: 'My Chart',
        html: '<html><body>Hello</body></html>',
      },
      timestamp: '2024-01-01T10:00:00Z',
    }

    const renderHtmlResult: ToolResult = {
      event_type: 'tool_result',
      tool_call_id: 'call_render_html',
      result_content: 'HTML rendered successfully',
      is_error: false,
      timestamp: '2024-01-01T10:00:05Z',
    }

    it('renders render_html as a standalone button (not expandable) when complete', () => {
      render(<ToolCallDisplay toolCall={renderHtmlToolCall} toolResult={renderHtmlResult} />)

      expect(screen.getByRole('button')).toBeInTheDocument()
      expect(screen.getByText('My Chart')).toBeInTheDocument()
      // Should NOT show standard expandable UI elements
      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
      expect(screen.queryByText('Result:')).not.toBeInTheDocument()
      expect(screen.queryByText('Running...')).not.toBeInTheDocument()
    })

    it('shows loading indicator for render_html while running', () => {
      render(<ToolCallDisplay toolCall={renderHtmlToolCall} />)

      expect(screen.getByText('Generating HTML...')).toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })

    it('shows error card for render_html on error', () => {
      const errorResult: ToolResult = {
        ...renderHtmlResult,
        is_error: true,
        result_content: 'Something went wrong',
      }

      render(<ToolCallDisplay toolCall={renderHtmlToolCall} toolResult={errorResult} />)

      expect(screen.getByText('Failed to render HTML')).toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })

    it('does not expand when render_html button is clicked', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={renderHtmlToolCall} toolResult={renderHtmlResult} />)

      await user.click(screen.getByRole('button'))

      // Standard expandable content should never appear
      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
      expect(screen.queryByText('Result:')).not.toBeInTheDocument()
    })
  })

  describe('Sub-Agent Conversation Button', () => {
    const taskToolCall: ToolCall = {
      event_type: 'tool_call',
      tool_call_id: 'call_task_1',
      tool_name: 'Task',
      tool_args: {
        description: 'Investigate auth module',
        prompt: 'Look into the auth module',
        subagent_type: 'Explore',
      },
      timestamp: '2024-01-01T10:00:00Z',
    }

    const taskResultWithAgentId: ToolResult = {
      event_type: 'tool_result',
      tool_call_id: 'call_task_1',
      result_content: 'Task completed successfully\nagentId: ac2a274\nTotal cost: $0.05',
      is_error: false,
      timestamp: '2024-01-01T10:00:30Z',
    }

    const taskResultWithoutAgentId: ToolResult = {
      event_type: 'tool_result',
      tool_call_id: 'call_task_1',
      result_content: 'Task completed successfully',
      is_error: false,
      timestamp: '2024-01-01T10:00:30Z',
    }

    it('shows view conversation button when Task tool has agentId and sessionId', () => {
      render(
        <ToolCallDisplay
          toolCall={taskToolCall}
          toolResult={taskResultWithAgentId}
          sessionId="parent-session-123"
        />
      )

      expect(screen.getByTitle('View sub-agent conversation')).toBeInTheDocument()
    })

    it('does not show view conversation button when sessionId is not provided', () => {
      render(
        <ToolCallDisplay
          toolCall={taskToolCall}
          toolResult={taskResultWithAgentId}
        />
      )

      expect(screen.queryByTitle('View sub-agent conversation')).not.toBeInTheDocument()
    })

    it('does not show view conversation button when result has no agentId', () => {
      render(
        <ToolCallDisplay
          toolCall={taskToolCall}
          toolResult={taskResultWithoutAgentId}
          sessionId="parent-session-123"
        />
      )

      expect(screen.queryByTitle('View sub-agent conversation')).not.toBeInTheDocument()
    })

    it('shows view conversation button when Agent tool has agentId and sessionId', () => {
      const agentToolCall: ToolCall = {
        ...taskToolCall,
        tool_name: 'Agent',
        tool_args: {
          description: 'Explore codebase structure',
          prompt: 'Look at the codebase',
          subagent_type: 'Explore',
        },
      }

      render(
        <ToolCallDisplay
          toolCall={agentToolCall}
          toolResult={taskResultWithAgentId}
          sessionId="parent-session-123"
        />
      )

      expect(screen.getByTitle('View sub-agent conversation')).toBeInTheDocument()
    })

    it('does not show view conversation button for non-sub-agent tools', () => {
      const nonSubAgentToolCall: ToolCall = {
        ...taskToolCall,
        tool_name: 'search_codebase',
      }

      render(
        <ToolCallDisplay
          toolCall={nonSubAgentToolCall}
          toolResult={taskResultWithAgentId}
          sessionId="parent-session-123"
        />
      )

      expect(screen.queryByTitle('View sub-agent conversation')).not.toBeInTheDocument()
    })

    it('does not show view conversation button when no result yet', () => {
      render(
        <ToolCallDisplay
          toolCall={taskToolCall}
          sessionId="parent-session-123"
        />
      )

      expect(screen.queryByTitle('View sub-agent conversation')).not.toBeInTheDocument()
    })

    it('opens sub-agent modal when view conversation button is clicked', async () => {
      const user = userEvent.setup()
      render(
        <ToolCallDisplay
          toolCall={taskToolCall}
          toolResult={taskResultWithAgentId}
          sessionId="parent-session-123"
        />
      )

      await user.click(screen.getByTitle('View sub-agent conversation'))

      const modal = screen.getByTestId('sub-agent-modal')
      expect(modal).toBeInTheDocument()
      expect(modal).toHaveAttribute('data-subtitle', 'ac2a274')
      expect(modal).toHaveTextContent('Investigate auth module')
    })

    it('passes subagentType to the modal', async () => {
      const user = userEvent.setup()
      render(
        <ToolCallDisplay
          toolCall={taskToolCall}
          toolResult={taskResultWithAgentId}
          sessionId="parent-session-123"
        />
      )

      await user.click(screen.getByTitle('View sub-agent conversation'))

      const modal = screen.getByTestId('sub-agent-modal')
      expect(modal).toHaveAttribute('data-subagent-type', 'Explore')
    })

    it('does not toggle expand/collapse when view conversation button is clicked', async () => {
      const user = userEvent.setup()
      render(
        <ToolCallDisplay
          toolCall={taskToolCall}
          toolResult={taskResultWithAgentId}
          sessionId="parent-session-123"
        />
      )

      // Click the view conversation button
      await user.click(screen.getByTitle('View sub-agent conversation'))

      // Should NOT expand (stopPropagation should prevent it)
      expect(screen.queryByText('Arguments:')).not.toBeInTheDocument()
    })

    it('uses fallback title when description is not in tool args', async () => {
      const user = userEvent.setup()
      const taskWithoutDescription: ToolCall = {
        ...taskToolCall,
        tool_args: { prompt: 'some prompt' },
      }

      render(
        <ToolCallDisplay
          toolCall={taskWithoutDescription}
          toolResult={taskResultWithAgentId}
          sessionId="parent-session-123"
        />
      )

      await user.click(screen.getByTitle('View sub-agent conversation'))

      const modal = screen.getByTestId('sub-agent-modal')
      expect(modal).toHaveTextContent('Sub-agent conversation')
    })
  })

  describe('DevBoard Sub-Agent Conversation Button', () => {
    const investigateToolCall: ToolCall = {
      event_type: 'tool_call',
      tool_call_id: 'call_investigate',
      tool_name: 'investigate_codebase',
      tool_args: { query: 'How does auth work?', codebase_name: 'backend' },
      timestamp: '2024-01-01T10:00:00Z',
    }

    const investigateResultWithConversationId: ToolResult = {
      event_type: 'tool_result',
      tool_call_id: 'call_investigate',
      result_content: JSON.stringify({
        result: '## Summary\n\nAuth uses JWT tokens.',
        conversation_id: 99,
      }),
      is_error: false,
      timestamp: '2024-01-01T10:00:30Z',
    }

    const investigateResultWithNullConversationId: ToolResult = {
      event_type: 'tool_result',
      tool_call_id: 'call_investigate',
      result_content: JSON.stringify({
        result: '## Summary\n\nAuth uses JWT tokens.',
        conversation_id: null,
      }),
      is_error: false,
      timestamp: '2024-01-01T10:00:30Z',
    }

    it('shows view conversation button when investigate_codebase has conversation_id', () => {
      render(
        <ToolCallDisplay
          toolCall={investigateToolCall}
          toolResult={investigateResultWithConversationId}
        />
      )

      expect(screen.getByTitle('View sub-agent conversation')).toBeInTheDocument()
    })

    it('does not show view conversation button when conversation_id is null', () => {
      render(
        <ToolCallDisplay
          toolCall={investigateToolCall}
          toolResult={investigateResultWithNullConversationId}
        />
      )

      expect(screen.queryByTitle('View sub-agent conversation')).not.toBeInTheDocument()
    })

    it('does not require sessionId prop for DevBoard sub-agent tools', () => {
      render(
        <ToolCallDisplay
          toolCall={investigateToolCall}
          toolResult={investigateResultWithConversationId}
        />
      )

      expect(screen.getByTitle('View sub-agent conversation')).toBeInTheDocument()
    })

    it('shows view conversation button for review_code_changes with conversation_id', () => {
      const reviewToolCall: ToolCall = {
        ...investigateToolCall,
        tool_call_id: 'call_review',
        tool_name: 'review_code_changes',
        tool_args: {},
      }
      const reviewResult: ToolResult = {
        event_type: 'tool_result',
        tool_call_id: 'call_review',
        result_content: JSON.stringify({
          result: '## Review\n\nLooks good.',
          conversation_id: 55,
        }),
        is_error: false,
        timestamp: '2024-01-01T10:00:30Z',
      }

      render(<ToolCallDisplay toolCall={reviewToolCall} toolResult={reviewResult} />)

      expect(screen.getByTitle('View sub-agent conversation')).toBeInTheDocument()
    })

    it('opens modal with Investigation title for investigate_codebase', async () => {
      const user = userEvent.setup()
      render(
        <ToolCallDisplay
          toolCall={investigateToolCall}
          toolResult={investigateResultWithConversationId}
        />
      )

      await user.click(screen.getByTitle('View sub-agent conversation'))

      const modal = screen.getByTestId('sub-agent-modal')
      expect(modal).toBeInTheDocument()
      expect(modal).toHaveTextContent('Investigation')
    })

    it('does not show view conversation button when no result yet', () => {
      render(<ToolCallDisplay toolCall={investigateToolCall} />)

      expect(screen.queryByTitle('View sub-agent conversation')).not.toBeInTheDocument()
    })
  })

  describe('Timing badge', () => {
    it('shows execution duration in header when tool result is present', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      // mockToolCall timestamp: 2024-01-01T10:00:00Z, mockToolResult: 2024-01-01T10:00:05Z => 5s
      expect(screen.getByText('5.0s')).toBeInTheDocument()
    })

    it('does not show execution duration when no tool result', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      // No result means no duration
      expect(screen.queryByText(/\d+\.\d+s/)).not.toBeInTheDocument()
    })

    it('shows HH:MM timing with opacity-0 group-hover class when previousEventTimestamp provided', () => {
      const { container } = render(
        <ToolCallDisplay
          toolCall={mockToolCall}
          toolResult={mockToolResult}
          previousEventTimestamp="2024-01-01T09:59:50Z"
        />
      )

      // The hover-reveal span should be initially hidden
      const hoverEl = container.querySelector('.opacity-0.group-hover\\:opacity-100')
      expect(hoverEl).toBeInTheDocument()
      // Should contain the delay — format is "HH:MM:SS (10.0s)"
      expect(hoverEl?.textContent).toContain('10.0s')
    })

    it('execution duration is visible in header and timing is a separate overlay', () => {
      const { container } = render(
        <ToolCallDisplay
          toolCall={mockToolCall}
          toolResult={mockToolResult}
          previousEventTimestamp="2024-01-01T10:00:00Z"
        />
      )

      // Exec duration is always visible in the header (not hidden)
      const execDurationEl = container.querySelector('.flex-shrink-0.text-\\[10px\\]')
      expect(execDurationEl).toBeInTheDocument()
      expect(execDurationEl).not.toHaveClass('opacity-0')

      // Timing overlay is separately positioned, initially hidden
      const hoverEl = container.querySelector('.opacity-0.group-hover\\:opacity-100')
      expect(hoverEl).toBeInTheDocument()
    })

    it('adds group class to tool call card container', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      const card = container.querySelector('[role="button"]')
      expect(card).toHaveClass('group')
    })
  })
})
