import { useState, useRef, useCallback, useEffect } from 'react'
import type { ConversationEvent } from '../../../lib/api'

export function useAutoScroll(
  messages: ConversationEvent[],
  pendingMessage: unknown,
  isRunningAction: boolean,
) {
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const isNearBottomRef = useRef(true)
  const [hasNewMessages, setHasNewMessages] = useState(false)

  const scrollToBottom = useCallback(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
      isNearBottomRef.current = true
      setHasNewMessages(false)
    }
  }, [])

  const handleScroll = useCallback(() => {
    const el = messagesContainerRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100
    isNearBottomRef.current = nearBottom
    if (nearBottom) {
      setHasNewMessages(false)
    }
  }, [])

  // Auto-scroll on new messages only when user is near bottom
  useEffect(() => {
    requestAnimationFrame(() => {
      if (isNearBottomRef.current) {
        scrollToBottom()
      } else {
        setHasNewMessages(true)
      }
    })
  }, [messages, scrollToBottom])

  // Always scroll to bottom for user-initiated actions
  useEffect(() => {
    requestAnimationFrame(() => {
      scrollToBottom()
    })
  }, [pendingMessage, isRunningAction, scrollToBottom])

  return { messagesContainerRef, handleScroll, scrollToBottom, hasNewMessages }
}
