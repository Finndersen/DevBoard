import type { ContextUsage } from '../../lib/api'
import { useConversationStreamStore } from '../../stores/conversationStreamStore'
import { useConversationStore } from '../../stores/conversationStore'
import { statusColors } from '../../styles/designSystem'

const AUTO_REFOCUS_THRESHOLD = 0.7

function formatTokenCount(n: number): string {
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`
  }
  if (n >= 1000) {
    return `${(n / 1000).toFixed(1)}K`
  }
  return String(n)
}

interface ContextUsageBadgeProps {
  contextUsage: ContextUsage
}

export function ContextUsageBadge({ contextUsage }: ContextUsageBadgeProps) {
  const total = contextUsage.cache_read_tokens + contextUsage.cache_write_tokens + contextUsage.input_tokens
  if (total === 0) return null

  const cachePercent = Math.round((contextUsage.cache_read_tokens / total) * 100)
  const totalFormatted = formatTokenCount(total)

  const contextWindow = contextUsage.context_window
  const utilization = contextWindow != null && contextWindow > 0
    ? contextUsage.input_tokens / contextWindow
    : null
  const utilizationPercent = utilization !== null ? Math.round(utilization * 100) : null
  const isWarning = utilization !== null && utilization >= AUTO_REFOCUS_THRESHOLD

  const tooltipParts = [
    `Input: ${contextUsage.input_tokens.toLocaleString()}`,
    `Output: ${contextUsage.output_tokens.toLocaleString()}`,
    `Cache read: ${contextUsage.cache_read_tokens.toLocaleString()}`,
    `Cache write: ${contextUsage.cache_write_tokens.toLocaleString()}`,
  ]
  if (contextWindow != null) {
    tooltipParts.push(`Context window: ${contextWindow.toLocaleString()}`)
  }
  if (utilizationPercent !== null) {
    tooltipParts.push(`Utilization: ${utilizationPercent}%`)
  }

  return (
    <span
      className={`text-xs flex items-center gap-1.5 ${isWarning ? statusColors.warning.text : 'text-gray-500 dark:text-gray-400'}`}
      title={tooltipParts.join(' · ')}
    >
      {totalFormatted} ctx · {cachePercent}% cached
      {utilizationPercent !== null && (
        <span className="flex items-center gap-1">
          <span className="text-gray-400 dark:text-gray-500">·</span>
          <span
            className={`font-medium ${isWarning ? statusColors.warning.text : 'text-gray-500 dark:text-gray-400'}`}
            data-testid="utilization-percent"
          >
            {utilizationPercent}% ctx
          </span>
          <span
            className="relative w-10 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden"
            role="progressbar"
            aria-valuenow={utilizationPercent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <span
              className={`absolute inset-y-0 left-0 rounded-full ${isWarning ? 'bg-amber-400 dark:bg-amber-500' : 'bg-blue-400 dark:bg-blue-500'}`}
              style={{ width: `${Math.min(utilizationPercent, 100)}%` }}
            />
          </span>
        </span>
      )}
    </span>
  )
}

interface ContextUsageDisplayProps {
  conversationId: number
}

export default function ContextUsageDisplay({ conversationId }: ContextUsageDisplayProps) {
  const contextUsage = useConversationStreamStore(
    state => state.conversationMessages.get(conversationId)?.contextUsage
  )
  const autoRefocus = useConversationStore(
    state => state.conversations.get(conversationId)?.autoRefocus ?? true
  )
  const setAutoRefocus = useConversationStore(state => state.setAutoRefocus)

  if (!contextUsage) return null

  return (
    <div className="flex items-center gap-2">
      <ContextUsageBadge contextUsage={contextUsage} />
      <button
        type="button"
        onClick={() => setAutoRefocus(conversationId, !autoRefocus)}
        className={`text-xs px-1.5 py-0.5 rounded border transition-colors ${
          autoRefocus
            ? 'border-blue-300 bg-blue-50 text-blue-600 dark:border-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
            : 'border-gray-200 bg-gray-50 text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-500'
        }`}
        title={autoRefocus
          ? 'Auto-refocus enabled — compact conversation when context is running low'
          : 'Auto-refocus disabled — click to enable'}
        aria-label={autoRefocus ? 'Auto-refocus on' : 'Auto-refocus off'}
        data-testid="auto-refocus-toggle"
      >
        ↺
      </button>
    </div>
  )
}
