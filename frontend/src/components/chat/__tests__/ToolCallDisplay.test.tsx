import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../../test/utils'
import ToolCallDisplay from '../ToolCallDisplay'
import type { ToolCall, ToolResult } from '../../../lib/api'

describe('ToolCallDisplay', () => {
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

      // Should show timestamp in header
      const formattedTime = new Date('2024-01-01T10:00:00Z').toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })
      expect(screen.getByText(formattedTime)).toBeInTheDocument()

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

    it('applies correct border color for running state', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('border-blue-600', 'bg-blue-50', 'dark:bg-blue-900/10')
    })

    it('applies correct border color for complete state', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('border-green-600', 'bg-green-50', 'dark:bg-green-900/10')
    })

    it('applies correct border color for error state', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockErrorResult} />)

      const button = screen.getByRole('button')
      expect(button).toHaveClass('border-red-600', 'bg-red-50', 'dark:bg-red-900/10')
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
      const resultContainer = errorContent.closest('.px-4')
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

  describe('Expanded State - Timestamps', () => {
    it('shows timestamp for tool call in header', () => {
      render(<ToolCallDisplay toolCall={mockToolCall} />)

      // formatTimestamp should format as HH:MM - shown in header (no need to expand)
      const formattedTime = new Date('2024-01-01T10:00:00Z').toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })

      expect(screen.getByText(formattedTime)).toBeInTheDocument()
    })

    it('shows timestamp for tool result when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      // Should show both tool call timestamp (in header) and result timestamp (in expanded section)
      const toolCallTime = new Date('2024-01-01T10:00:00Z').toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })
      const resultTime = new Date('2024-01-01T10:00:05Z').toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })

      expect(screen.getByText(toolCallTime)).toBeInTheDocument()

      // Result timestamp is shown with "Returned: " prefix
      expect(screen.getByText(`Returned: ${resultTime}`)).toBeInTheDocument()
    })

    it('shows proper visual hierarchy with timestamps when expanded', async () => {
      const user = userEvent.setup()
      render(<ToolCallDisplay toolCall={mockToolCall} toolResult={mockToolResult} />)

      await user.click(screen.getByRole('button'))

      const toolCallTime = new Date('2024-01-01T10:00:00Z').toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })
      const resultTime = new Date('2024-01-01T10:00:05Z').toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })

      // Check the call timestamp styling with theme-aware classes
      const callTimestamp = screen.getByText(toolCallTime)
      expect(callTimestamp).toHaveClass('text-xs', 'text-gray-600', 'dark:text-gray-500')

      // Check result timestamp styling with theme-aware classes (includes "Returned: " prefix)
      const resultTimestamp = screen.getByText(`Returned: ${resultTime}`)
      expect(resultTimestamp).toHaveClass('text-xs', 'text-gray-600', 'dark:text-gray-500')
    })
  })

  describe('Layout and Styling', () => {
    it('limits width to 80% of container', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      const wrapper = container.querySelector('.max-w-\\[80\\%\\]')
      expect(wrapper).toBeInTheDocument()
    })

    it('aligns tool call to the left', () => {
      const { container } = render(<ToolCallDisplay toolCall={mockToolCall} />)

      const outerContainer = container.querySelector('.justify-start')
      expect(outerContainer).toBeInTheDocument()

      const innerContainer = container.querySelector('.items-start')
      expect(innerContainer).toBeInTheDocument()
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
})
