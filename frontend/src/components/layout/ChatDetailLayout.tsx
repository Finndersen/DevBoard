import { useState, useCallback, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import CollapsedPanelStrip from '../ui/CollapsedPanelStrip'

const MIN_CHAT_WIDTH = 500
const MIN_DETAILS_WIDTH = 700
const DIVIDER_WIDTH = 8
const NARROW_THRESHOLD = MIN_CHAT_WIDTH + MIN_DETAILS_WIDTH + DIVIDER_WIDTH

interface ChatDetailLayoutProps {
  chatContent: ReactNode
  detailsContent: ReactNode
  actionBar: ReactNode
  expandedPanel: 'chat' | 'details'
  onExpandPanel: (panel: 'chat' | 'details') => void
  chatStripProps: {
    isStreaming: boolean
    needsAttention: boolean
  }
  detailsStripProps: {
    needsAttention: boolean
  }
  onNarrowChange?: (isNarrow: boolean) => void
  hideDetails?: boolean
}

export default function ChatDetailLayout({
  chatContent,
  detailsContent,
  actionBar,
  expandedPanel,
  onExpandPanel,
  chatStripProps,
  detailsStripProps,
  onNarrowChange,
  hideDetails = false,
}: ChatDetailLayoutProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isNarrow, setIsNarrow] = useState(false)
  // Chat panel width as fraction of available space (initial ratio from minimums)
  const [chatFraction, setChatFraction] = useState(MIN_CHAT_WIDTH / (MIN_CHAT_WIDTH + MIN_DETAILS_WIDTH))
  const isDragging = useRef(false)

  // Observe container width to determine narrow/wide mode
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new ResizeObserver(([entry]) => {
      const narrow = entry.contentRect.width < NARROW_THRESHOLD
      setIsNarrow(prev => {
        if (prev !== narrow) {
          onNarrowChange?.(narrow)
        }
        return narrow
      })
    })

    observer.observe(el)
    return () => observer.disconnect()
  }, [onNarrowChange])

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const container = containerRef.current
    if (!container) return

    const onMouseMove = (moveEvent: MouseEvent) => {
      if (!isDragging.current) return
      const rect = container.getBoundingClientRect()
      // Account for container padding (p-2 = 8px each side)
      const padding = 8
      const availableWidth = rect.width - padding * 2 - DIVIDER_WIDTH
      const mouseX = moveEvent.clientX - rect.left - padding

      // Clamp to minimum widths
      const minChatFrac = MIN_CHAT_WIDTH / availableWidth
      const maxChatFrac = (availableWidth - MIN_DETAILS_WIDTH) / availableWidth
      const fraction = Math.max(minChatFrac, Math.min(maxChatFrac, mouseX / availableWidth))
      setChatFraction(fraction)
    }

    const onMouseUp = () => {
      isDragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [])

  return (
    <div ref={containerRef} className="flex flex-col flex-1 min-h-0 overflow-hidden px-1 py-1.5 gap-1.5">
      {hideDetails ? (
        // Chat-only mode: no details panel
        <div className="flex-1 min-h-0 overflow-hidden">
          {chatContent}
        </div>
      ) : isNarrow ? (
        // Narrow mode: Collapsible panels
        <div className="flex gap-2 flex-1 min-h-0 overflow-hidden">
          {/* Chat panel */}
          <div
            className="relative h-full overflow-hidden transition-[flex] duration-200 ease-in-out"
            style={{ flex: expandedPanel === 'chat' ? '1 1 0%' : '0 0 2.5rem' }}
          >
            <div className={`h-full min-w-0 ${expandedPanel !== 'chat' ? 'invisible' : ''}`}>
              {chatContent}
            </div>
            {expandedPanel !== 'chat' && (
              <div className="absolute inset-0">
                <CollapsedPanelStrip
                  variant="chat"
                  icon="💬"
                  label="Chat"
                  isStreaming={chatStripProps.isStreaming}
                  needsAttention={chatStripProps.needsAttention}
                  onClick={() => onExpandPanel('chat')}
                  className="h-full"
                />
              </div>
            )}
          </div>

          {/* Details panel */}
          <div
            className="relative h-full overflow-hidden transition-[flex] duration-200 ease-in-out"
            style={{ flex: expandedPanel === 'details' ? '1 1 0%' : '0 0 2.5rem' }}
          >
            <div className={`h-full min-w-0 ${expandedPanel !== 'details' ? 'invisible' : ''}`}>
              {detailsContent}
            </div>
            {expandedPanel !== 'details' && (
              <div className="absolute inset-0">
                <CollapsedPanelStrip
                  variant="details"
                  icon="📄"
                  label="Details"
                  needsAttention={detailsStripProps.needsAttention}
                  onClick={() => onExpandPanel('details')}
                  className="h-full"
                />
              </div>
            )}
          </div>
        </div>
      ) : (
        // Wide mode: Resizable side-by-side panels
        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Chat panel */}
          <div
            className="h-full overflow-hidden"
            style={{ width: `calc(${chatFraction * 100}% - ${DIVIDER_WIDTH / 2}px)`, flexShrink: 0 }}
          >
            {chatContent}
          </div>

          {/* Draggable divider */}
          <div
            className="flex-shrink-0 flex items-center justify-center cursor-col-resize group hover:bg-blue-500/10 transition-colors rounded"
            style={{ width: DIVIDER_WIDTH }}
            onMouseDown={handleDragStart}
          >
            <div className="w-0.5 h-8 bg-gray-600 rounded-full group-hover:bg-blue-400 transition-colors" />
          </div>

          {/* Details panel */}
          <div className="flex-1 h-full overflow-hidden min-w-0">
            {detailsContent}
          </div>
        </div>
      )}

      {/* Action bar - full width, aligned with panels */}
      {actionBar}
    </div>
  )
}
