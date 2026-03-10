import { useState, useRef, useEffect, type ReactNode } from 'react'

interface AgentBlockDisplayProps {
  children: ReactNode
  isLatest: boolean
}

const MAX_COLLAPSED_HEIGHT = 400

export default function AgentBlockDisplay({ children, isLatest }: AgentBlockDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [needsExpansion, setNeedsExpansion] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isLatest || !contentRef.current) {
      setNeedsExpansion(false)
      return
    }

    const observer = new ResizeObserver(() => {
      if (contentRef.current) {
        setNeedsExpansion(contentRef.current.scrollHeight > MAX_COLLAPSED_HEIGHT)
      }
    })

    observer.observe(contentRef.current)
    return () => observer.disconnect()
  }, [isLatest])

  return (
    <div className="flex flex-col">
      <div className="relative">
        <div
          ref={contentRef}
          className="overflow-hidden transition-all duration-300"
          style={{
            maxHeight: !isExpanded && needsExpansion ? `${MAX_COLLAPSED_HEIGHT}px` : undefined
          }}
        >
          {children}
        </div>
        {needsExpansion && !isExpanded && (
          <div className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none bg-gradient-to-t from-white dark:from-gray-900 to-transparent" />
        )}
      </div>
      {needsExpansion && (
        <div className="flex justify-center mt-1">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-xs font-medium hover:underline text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
          >
            {isExpanded ? '▲ Show less' : '▼ Show more'}
          </button>
        </div>
      )}
    </div>
  )
}
