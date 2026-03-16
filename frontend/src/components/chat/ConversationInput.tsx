import { useRef, useEffect, useCallback, useMemo, useState } from 'react'
import { PaperAirplaneIcon, StopIcon, XMarkIcon, ClockIcon } from '@heroicons/react/24/outline'
import { standardChatInputClasses } from '../../styles/inputStyles'

const MAX_TEXTAREA_ROWS = 10
const STREAMING_PLACEHOLDER = "Type a message and press Enter to queue (sends when agent finishes)..."

interface ConversationInputProps {
  value: string
  onChange: (value: string) => void
  onSendMessage: () => void
  placeholder?: string
  isStreaming?: boolean
  onStopStream?: () => void
  isQueued?: boolean
}

export default function ConversationInput({
  value,
  onChange,
  onSendMessage,
  placeholder = "Ask a question...",
  isStreaming = false,
  onStopStream,
  isQueued = false,
}: ConversationInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const cachedLineHeightRef = useRef<number | null>(null)
  const heightAdjustmentTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [needsScroll, setNeedsScroll] = useState(false)

  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    if (cachedLineHeightRef.current === null) {
      const computedStyle = window.getComputedStyle(textarea)
      cachedLineHeightRef.current = parseInt(computedStyle.lineHeight)
    }

    const lineHeight = cachedLineHeightRef.current
    const maxHeight = lineHeight * MAX_TEXTAREA_ROWS

    textarea.style.height = 'auto'
    const scrollHeight = textarea.scrollHeight
    const newHeight = Math.min(scrollHeight, maxHeight)
    textarea.style.height = `${newHeight}px`

    setNeedsScroll(scrollHeight > maxHeight)
  }, [])

  useEffect(() => {
    if (heightAdjustmentTimeoutRef.current) {
      clearTimeout(heightAdjustmentTimeoutRef.current)
    }

    heightAdjustmentTimeoutRef.current = setTimeout(() => {
      adjustTextareaHeight()
    }, 150)

    return () => {
      if (heightAdjustmentTimeoutRef.current) {
        clearTimeout(heightAdjustmentTimeoutRef.current)
      }
    }
  }, [value, adjustTextareaHeight])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
  }, [onChange])

  const handleClear = useCallback(() => {
    onChange('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    cachedLineHeightRef.current = null
    setNeedsScroll(false)
    textareaRef.current?.focus()
  }, [onChange])

  const handleSendMessage = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    const messageText = value.trim()
    if (!messageText) return

    onSendMessage()
  }, [value, onSendMessage])

  const handleInputKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage(e as unknown as React.FormEvent)
    }
  }, [handleSendMessage])

  const isSendDisabled = useMemo(
    () => !value.trim(),
    [value]
  )

  const hasText = value.trim().length > 0

  const effectivePlaceholder = isStreaming && !isQueued ? STREAMING_PLACEHOLDER : placeholder

  return (
    <form onSubmit={handleSendMessage} className="flex space-x-2 items-end">
      <div className="flex-1 relative flex items-end">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInputChange}
          onKeyDown={handleInputKeyDown}
          placeholder={effectivePlaceholder}
          className={`w-full resize-none ${needsScroll ? 'overflow-y-auto' : 'overflow-hidden'} ${standardChatInputClasses} ${hasText ? 'pr-8' : ''} ${isQueued ? 'border-l-2 border-l-amber-400 dark:border-l-amber-500 bg-amber-50/50 dark:bg-amber-900/10 text-opacity-70' : ''}`}
          rows={1}
        />
        {hasText && (
          <button
            type="button"
            onClick={handleClear}
            aria-label="Clear input"
            className="absolute right-2 bottom-2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        )}
      </div>
      {isStreaming ? (
        <div className="flex items-center space-x-2 flex-shrink-0">
          {isQueued && (
            <div className="flex items-center space-x-1 px-3 py-2 bg-amber-100 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 rounded-md">
              <ClockIcon className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <span className="text-xs font-medium text-amber-700 dark:text-amber-300">Queued</span>
            </div>
          )}
          <button
            type="button"
            onClick={onStopStream}
            aria-label="Stop streaming"
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            <StopIcon className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <button
          type="submit"
          disabled={isSendDisabled}
          aria-label="Send message"
          className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
        >
          <PaperAirplaneIcon className="w-4 h-4" />
        </button>
      )}
    </form>
  )
}
