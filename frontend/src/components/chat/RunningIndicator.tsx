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

  if (!isStreaming) return null

  return (
    <div className="flex items-center gap-1.5 ml-3 text-sm text-green-600 dark:text-green-400">
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
      </span>
      <span className="font-medium">Running</span>
      {elapsed && <span className="text-green-500 dark:text-green-500">· {elapsed}</span>}
    </div>
  )
}
