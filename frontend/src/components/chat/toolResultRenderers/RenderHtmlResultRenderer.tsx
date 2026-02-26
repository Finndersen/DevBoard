/**
 * Rich renderer for render_html tool results.
 * Displays a preview card with title and button to open HTML content in a modal.
 */

import { useState } from 'react'

import type { RichResultRendererProps } from './index'
import HtmlRenderModal from '../../ui/HtmlRenderModal'

/**
 * Expected data shape from the render_html tool.
 */
interface RenderHtmlResultData {
  title: string
  html: string
}

/**
 * Type guard to validate the data shape.
 */
function isRenderHtmlResultData(data: unknown): data is RenderHtmlResultData {
  if (typeof data !== 'object' || data === null) {
    return false
  }

  const obj = data as Record<string, unknown>
  return typeof obj.title === 'string' && typeof obj.html === 'string'
}

export default function RenderHtmlResultRenderer({ data }: RichResultRendererProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)

  if (!isRenderHtmlResultData(data)) {
    return (
      <div className="text-xs text-red-600 dark:text-red-400">
        Invalid HTML render data format
      </div>
    )
  }

  return (
    <>
      <div className="text-xs space-y-2">
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-purple-600 dark:text-purple-400 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"
            />
          </svg>
          <span className="text-purple-700 dark:text-purple-300 font-medium">
            {data.title}
          </span>
        </div>

        <div className="pl-6 pt-1">
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-900/30 border border-purple-200 dark:border-purple-700 rounded hover:bg-purple-100 dark:hover:bg-purple-900/50 transition-colors"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
              />
            </svg>
            Open
          </button>
        </div>
      </div>

      <HtmlRenderModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={data.title}
        html={data.html}
      />
    </>
  )
}
