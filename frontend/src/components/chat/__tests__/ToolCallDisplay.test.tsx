import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render, mockNavigate } from '../../../test/utils'
import ToolCallDisplay from '../ToolCallDisplay'
import type { ToolCall, ToolResult } from '../../../lib/api'

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

    it('uses neutral gray styling regardless of state', () => {
      const { rerender } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('border-gray-300', 'bg-gray-50')

      rerender(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)
      expect(button).toHaveClass('border-gray-300', 'bg-gray-50')

      rerender(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockErrorResult} />)
      expect(button).toHaveClass('border-gray-300', 'bg-gray-50')
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
      expect(resultContainer).toHaveClass('border-red-300', 'dark:border-red-800', 'bg-red-100', 'dark:bg-red-900/10')
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

      // Duration between 10:00:00 and 10:00:05 should be 5.0s
      expect(screen.getByText('5.0s')).toBeInTheDocument()
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

      // Duration should be 234ms
      expect(screen.getByText('234ms')).toBeInTheDocument()
    })

    it('shows duration with correct styling', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      // Check duration styling with theme-aware classes
      const duration = screen.getByText('5.0s')
      expect(duration).toHaveClass('text-xs', 'text-gray-600', 'dark:text-gray-500')
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

    it('has appropriate shadow and border styling', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('shadow-sm', 'border', 'overflow-hidden')
    })

    it('applies hover effect to button', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('hover:opacity-80', 'transition-opacity')
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
})
