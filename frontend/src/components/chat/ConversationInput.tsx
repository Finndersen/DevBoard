import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { PaperAirplaneIcon } from '@heroicons/react/24/outline'
import { standardChatInputClasses } from '../../styles/inputStyles'

const MAX_TEXTAREA_ROWS = 10

interface ConversationInputProps {
  onSendMessage: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function ConversationInput({
  onSendMessage,
  disabled = false,
  placeholder = "Ask a question..."
}: ConversationInputProps) {
  const [newMessage, setNewMessage] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Cache line height to avoid repeated DOM queries on every keystroke
  const cachedLineHeightRef = useRef<number | null>(null)
  // Debounce timeout for textarea height adjustment
  const heightAdjustmentTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-resize textarea based on content (optimized to minimize layout thrashing)
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (!textarea) return

    // Get or cache line height to avoid repeated DOM queries
    if (cachedLineHeightRef.current === null) {
      const computedStyle = window.getComputedStyle(textarea)
      cachedLineHeightRef.current = parseInt(computedStyle.lineHeight)
    }

    const lineHeight = cachedLineHeightRef.current
    const maxHeight = lineHeight * MAX_TEXTAREA_ROWS

    // Batch DOM operations: read scrollHeight, then write height in one operation
    textarea.style.height = 'auto'
    const scrollHeight = textarea.scrollHeight
    const newHeight = Math.min(scrollHeight, maxHeight)
    textarea.style.height = `${newHeight}px`
  }, [])

  // Debounce the height adjustment to reduce layout thrashing during fast typing
  // Keep input value updates immediate, but defer visual height adjustment
  useEffect(() => {
    // Clear any pending adjustment
    if (heightAdjustmentTimeoutRef.current) {
      clearTimeout(heightAdjustmentTimeoutRef.current)
    }

    // Schedule the height adjustment for 150ms after typing stops
    heightAdjustmentTimeoutRef.current = setTimeout(() => {
      adjustTextareaHeight()
    }, 150)

    return () => {
      if (heightAdjustmentTimeoutRef.current) {
        clearTimeout(heightAdjustmentTimeoutRef.current)
      }
    }
  }, [newMessage, adjustTextareaHeight])

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewMessage(e.target.value)
  }, [])

  const handleSendMessage = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    const messageText = newMessage.trim()
    if (!messageText) return

    // Call parent callback with message
    onSendMessage(messageText)

    // Clear the input locally
    setNewMessage('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
    // Reset cached line height in case font size changed
    cachedLineHeightRef.current = null
    // Focus back to textarea
    textareaRef.current?.focus()
  }, [newMessage, onSendMessage])

  const handleInputKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage(e as unknown as React.FormEvent)
    }
  }, [handleSendMessage])

  const isButtonDisabled = useMemo(
    () => !newMessage.trim() || disabled,
    [newMessage, disabled]
  )

  return (
    <form onSubmit={handleSendMessage} className="flex space-x-2 items-end">
      <textarea
        ref={textareaRef}
        value={newMessage}
        onChange={handleInputChange}
        onKeyDown={handleInputKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className={`flex-1 resize-none overflow-y-auto ${standardChatInputClasses}`}
        rows={1}
      />
      <button
        type="submit"
        disabled={isButtonDisabled}
        aria-label="Send message"
        className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
      >
        <PaperAirplaneIcon className="w-4 h-4" />
      </button>
    </form>
  )
}
