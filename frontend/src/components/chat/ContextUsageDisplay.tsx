import { useConversationStreamStore } from '../../stores/conversationStreamStore'

interface ContextUsageDisplayProps {
  conversationId: number
}

function formatTokenCount(n: number): string {
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`
  }
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}K`
  }
  return String(n)
}

export default function ContextUsageDisplay({ conversationId }: ContextUsageDisplayProps) {
  const contextUsage = useConversationStreamStore(
    state => state.conversationMessages.get(conversationId)?.contextUsage
  )

  if (!contextUsage) return null

  // Total context sent to model: uncached input + cached reads + cache writes (excludes output)
  const total = contextUsage.cache_read_tokens + contextUsage.cache_write_tokens + contextUsage.input_tokens
  if (total === 0) return null

  const cachePercent = Math.round((contextUsage.cache_read_tokens / total) * 100)
  const totalFormatted = formatTokenCount(total)

  return (
    <span
      className="text-xs text-gray-500 dark:text-gray-400"
      title={`Input: ${contextUsage.input_tokens.toLocaleString()} · Output: ${contextUsage.output_tokens.toLocaleString()} · Cache read: ${contextUsage.cache_read_tokens.toLocaleString()} · Cache write: ${contextUsage.cache_write_tokens.toLocaleString()}`}
    >
      {totalFormatted} ctx · {cachePercent}% cached
    </span>
  )
}
