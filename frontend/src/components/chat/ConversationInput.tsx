import { useRef, useEffect, useCallback, useMemo } from 'react'
import { PaperAirplaneIcon, StopIcon, XMarkIcon, ClockIcon } from '@heroicons/react/24/outline'
import { standardChatInputClasses } from '../../styles/inputStyles'

const MAX_TEXTAREA_ROWS = 10

interface ConversationInputProps {
  value: string
  onChange: (value: string) => void
  onSendMessage: () => void
  placeholder?: string
  isStreaming?: boolean
  onStopStream?: () => void
  isQueued?: boolean
  onCancelQueue?: () => void
}

export default function ConversationInput({
  value,
  onChange,
  onSendMessage,
  placeholder = "Ask a question...",
  isStreaming = false,
  onStopStream,
  isQueued = false,
  onCancelQueue
}: ConversationInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const cachedLineHeightRef = useRef<number | null>(null)
  const heightAdjustmentTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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

  return (
    <form onSubmit={handleSendMessage} className="flex space-x-2 items-end">
      <div className="flex-1 relative">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInputChange}
          onKeyDown={handleInputKeyDown}
          placeholder={placeholder}
          className={`w-full resize-none overflow-y-auto ${standardChatInputClasses} ${hasText ? 'pr-8' : ''}`}
          rows={1}
        />
        {hasText && (
          <button
            type="button"
            onClick={handleClear}
            aria-label="Clear input"
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        )}
      </div>
      {isStreaming ? (
        isQueued ? (
          <div className="flex items-center space-x-2 flex-shrink-0">
            <div className="flex items-center space-x-1 px-3 py-2 bg-amber-100 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 rounded-md">
              <ClockIcon className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              <span className="text-xs font-medium text-amber-700 dark:text-amber-300">Queued</span>
            </div>
            <button
              type="button"
              onClick={onCancelQueue}
              aria-label="Cancel queued message"
              className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-gray-500 hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-400"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={onStopStream}
            aria-label="Stop streaming"
            className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 flex-shrink-0"
          >
            <StopIcon className="w-4 h-4" />
          </button>
        )
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
