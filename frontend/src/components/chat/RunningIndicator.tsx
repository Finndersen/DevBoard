import { useState, useEffect } from 'react'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'

interface RunningIndicatorProps {
  conversationId: number
}

function formatElapsed(startedAt: number): string {
  const diffMs = Date.now() - startedAt
  const totalSeconds = Math.floor(diffMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  if (minutes === 0) return `${seconds}s`
  return `${minutes}m ${seconds.toString().padStart(2, '0')}s`
}

export default function RunningIndicator({ conversationId }: RunningIndicatorProps) {
  const streamState = useConversationStreamStore(
    state => state.activeStreams.get(conversationId)
  )
  const isStreaming = streamState?.isStreaming ?? false
  const startedAt = streamState?.startedAt

  const [elapsed, setElapsed] = useState('')

  useEffect(() => {
    if (!isStreaming || !startedAt) {
      setElapsed('')
      return
    }

    setElapsed(formatElapsed(startedAt))
    const interval = setInterval(() => {
      setElapsed(formatElapsed(startedAt))
    }, 1000)

    return () => clearInterval(interval)
  }, [isStreaming, startedAt])

  if (isStreaming) {
    return (
      <div className="flex items-center gap-1.5 ml-3">
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
        </span>
        {elapsed && <span className="text-sm text-gray-400 dark:text-gray-500">{elapsed}</span>}
      </div>
    )
  }

  if (streamState?.error) {
    return (
      <div className="flex items-center gap-1.5 ml-3 text-red-500 dark:text-red-400">
        <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span className="text-sm">Agent error</span>
      </div>
    )
  }

  return null
}
