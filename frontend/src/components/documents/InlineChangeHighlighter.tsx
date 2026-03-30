import type { HighlightedChange } from '../../utils/diffUtils'
import { surfaces, borderColors, statusColors, textColors } from '../../styles/designSystem'

interface InlineChangeHighlighterProps {
  changes: HighlightedChange[]
  className?: string
  showWhitespace?: boolean
}

export default function InlineChangeHighlighter({ 
  changes, 
  className = '',
  showWhitespace = false 
}: InlineChangeHighlighterProps) {
  const renderChange = (change: HighlightedChange, index: number) => {
    let displayValue = change.value
    
    // Show whitespace characters if enabled
    if (showWhitespace) {
      displayValue = displayValue
        .replace(/ /g, '·')
        .replace(/\t/g, '→')
        .replace(/\n/g, '¶\n')
    }

    const baseClasses = 'transition-colors duration-150'
    
    switch (change.type) {
      case 'added':
        return (
          <span
            key={index}
            className={`${baseClasses} ${statusColors.success.icon} ${statusColors.success.text} px-0.5 rounded-sm`}
            title="Added text"
          >
            {displayValue}
          </span>
        )

      case 'removed':
        return (
          <span
            key={index}
            className={`${baseClasses} ${statusColors.error.icon} ${statusColors.error.text} px-0.5 rounded-sm line-through opacity-70`}
            title="Removed text"
          >
            {displayValue}
          </span>
        )

      case 'unchanged':
      default:
        return (
          <span key={index} className={textColors.secondary}>
            {displayValue}
          </span>
        )
    }
  }

  return (
    <pre className={`font-mono leading-relaxed whitespace-pre-wrap ${className}`}>
      {changes.map(renderChange)}
    </pre>
  )
}

// Wrapper component for simple before/after comparison
interface ChangeComparisonProps {
  oldText: string
  newText: string
  changes: HighlightedChange[]
  title?: string
  className?: string
}

export function ChangeComparison({ 
  oldText, 
  newText: _newText, // eslint-disable-line @typescript-eslint/no-unused-vars
  changes, 
  title,
  className = '' 
}: ChangeComparisonProps) {
  return (
    <div className={`border ${borderColors.default} rounded-lg overflow-hidden ${className}`}>
      {title && (
        <div className={`${surfaces.sunken} px-4 py-2 border-b ${borderColors.default}`}>
          <span className={`text-sm font-medium ${textColors.secondary}`}>
            {title}
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2">
        {/* Before (Old) */}
        <div className={`border-r ${borderColors.default}`}>
          <div className={`${statusColors.error.bg} px-4 py-2 border-b ${statusColors.error.border}`}>
            <span className={`text-xs font-medium ${statusColors.error.text}`}>
              Before:
            </span>
          </div>
          <div className="p-4 bg-red-50/50 dark:bg-red-900/10 min-h-[4rem] max-h-48 overflow-auto">
            <pre className={`text-xs ${statusColors.error.text} whitespace-pre-wrap font-mono`}>
              {oldText}
            </pre>
          </div>
        </div>

        {/* After (New) with highlighting */}
        <div>
          <div className={`${statusColors.success.bg} px-4 py-2 border-b ${statusColors.success.border}`}>
            <span className={`text-xs font-medium ${statusColors.success.text}`}>
              After (with changes highlighted):
            </span>
          </div>
          <div className="p-4 bg-green-50/50 dark:bg-green-900/10 min-h-[4rem] max-h-48 overflow-auto">
            <InlineChangeHighlighter
              changes={changes}
              className={`text-xs ${statusColors.success.text}`}
            />
          </div>
        </div>
      </div>
    </div>
  )
}