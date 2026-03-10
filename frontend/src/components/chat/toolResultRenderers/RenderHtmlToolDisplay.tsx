/**
 * Custom display for render_html tool calls.
 * Replaces the standard collapsible ToolCallDisplay with a standalone button
 * that opens the HTML content in a modal.
 */

import { useState } from 'react'

import type { CustomToolDisplayProps } from './index'
import HtmlRenderModal from '../../ui/HtmlRenderModal'

export default function RenderHtmlToolDisplay({ toolCall, toolResult }: CustomToolDisplayProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)

  const args = toolCall.tool_args as Record<string, unknown> | null
  const title = typeof args?.title === 'string' ? args.title : 'HTML Content'
  const html = typeof args?.html === 'string' ? args.html : ''

  const isError = toolResult?.is_error === true
  const isRunning = toolResult === undefined

  if (isRunning) {
    return (
      <div className="flex w-full min-w-0">
        <div className="rounded-md px-3 py-1.5 flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span className="text-sm text-blue-600 dark:text-blue-400">Generating HTML...</span>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex w-full min-w-0">
        <div className="rounded-md px-3 py-1.5 flex items-center gap-2">
          <svg className="w-4 h-4 text-red-600 dark:text-red-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          <span className="text-sm text-red-700 dark:text-red-400">Failed to render HTML</span>
          {toolResult?.result_content && (
            <span className="text-xs text-red-600 dark:text-red-300 truncate">{toolResult.result_content}</span>
          )}
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="flex w-full min-w-0">
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="rounded-md px-3 py-1.5 flex items-center gap-2 hover:bg-gray-100 dark:hover:bg-gray-800/30 transition-colors text-left"
        >
          <svg
            className="w-4 h-4 text-purple-600 dark:text-purple-400 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          <span className="text-sm font-medium text-purple-700 dark:text-purple-300 truncate">{title}</span>
          <svg
            className="w-3.5 h-3.5 text-purple-500 dark:text-purple-400 flex-shrink-0 ml-1"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </button>
      </div>

      <HtmlRenderModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={title}
        html={html}
      />
    </>
  )
}
