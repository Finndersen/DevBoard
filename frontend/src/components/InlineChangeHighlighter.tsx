import type { HighlightedChange } from '../utils/diffUtils'

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
            className={`${baseClasses} bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 px-0.5 rounded-sm`}
            title="Added text"
          >
            {displayValue}
          </span>
        )
      
      case 'removed':
        return (
          <span 
            key={index}
            className={`${baseClasses} bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 px-0.5 rounded-sm line-through opacity-70`}
            title="Removed text"
          >
            {displayValue}
          </span>
        )
      
      case 'unchanged':
      default:
        return (
          <span key={index} className="text-gray-700 dark:text-gray-300">
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
  newText, 
  changes, 
  title,
  className = '' 
}: ChangeComparisonProps) {
  return (
    <div className={`border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden ${className}`}>
      {title && (
        <div className="bg-gray-50 dark:bg-gray-800 px-4 py-2 border-b border-gray-200 dark:border-gray-700">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            {title}
          </span>
        </div>
      )}
      
      <div className="grid grid-cols-1 lg:grid-cols-2">
        {/* Before (Old) */}
        <div className="border-r border-gray-200 dark:border-gray-700">
          <div className="bg-red-50 dark:bg-red-900/20 px-4 py-2 border-b border-red-200 dark:border-red-800">
            <span className="text-xs font-medium text-red-700 dark:text-red-400">
              Before:
            </span>
          </div>
          <div className="p-4 bg-red-50/50 dark:bg-red-900/10 min-h-[4rem] max-h-48 overflow-auto">
            <pre className="text-xs text-red-800 dark:text-red-200 whitespace-pre-wrap font-mono">
              {oldText}
            </pre>
          </div>
        </div>

        {/* After (New) with highlighting */}
        <div>
          <div className="bg-green-50 dark:bg-green-900/20 px-4 py-2 border-b border-green-200 dark:border-green-800">
            <span className="text-xs font-medium text-green-700 dark:text-green-400">
              After (with changes highlighted):
            </span>
          </div>
          <div className="p-4 bg-green-50/50 dark:bg-green-900/10 min-h-[4rem] max-h-48 overflow-auto">
            <InlineChangeHighlighter 
              changes={changes}
              className="text-xs text-green-800 dark:text-green-200"
            />
          </div>
        </div>
      </div>
    </div>
  )
}