import { borderColors, surfaces, hoverColors, textColors } from '../../styles/designSystem'

interface CollapsedPanelStripProps {
  icon: React.ReactNode
  label: string
  onClick: () => void
  isStreaming?: boolean
  needsAttention?: boolean
  variant: 'chat' | 'details'
  className?: string
}

export default function CollapsedPanelStrip({
  icon,
  label,
  onClick,
  isStreaming = false,
  needsAttention = false,
  variant,
  className = '',
}: CollapsedPanelStripProps) {
  const showStreamingDot = variant === 'chat' && isStreaming
  const showAttentionDot = needsAttention && !showStreamingDot
  const highlightStrip = needsAttention && !showStreamingDot

  return (
    <div
      onClick={onClick}
      className={`
        w-10 flex-shrink-0 rounded-lg border cursor-pointer
        transition-all duration-200
        ${highlightStrip
          ? 'border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/15'
          : `${borderColors.default} ${surfaces.raised} hover:border-blue-400 dark:hover:border-blue-500 ${hoverColors.subtle}`
        }
        ${needsAttention && !showStreamingDot ? 'animate-attention-pulse' : ''}
        ${className}
      `}
    >
      <div
        className="flex items-center justify-center h-full gap-2 text-xs font-medium px-1"
        style={{ writingMode: 'vertical-rl' }}
      >
        <span style={{ writingMode: 'horizontal-tb' }}>{icon}</span>
        <span className={highlightStrip ? 'text-blue-600 dark:text-blue-400' : textColors.muted}>
          {label}
        </span>
        {showStreamingDot && (
          <span className="relative flex h-2 w-2 shrink-0" style={{ writingMode: 'horizontal-tb' }}>
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
          </span>
        )}
        {showAttentionDot && (
          <span
            className="inline-flex rounded-full h-2 w-2 bg-blue-500 shrink-0"
            style={{ writingMode: 'horizontal-tb' }}
          />
        )}
      </div>
    </div>
  )
}
