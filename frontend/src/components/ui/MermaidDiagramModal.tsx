import { useState, useRef, useCallback, useEffect } from 'react'
import {
  ClipboardDocumentIcon,
  CheckIcon,
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'
import Modal from './Modal'
import MermaidDiagram from './MermaidDiagram'
import CodeBlock from './CodeBlock'

interface MermaidDiagramModalProps {
  isOpen: boolean
  onClose: () => void
  code: string
}

const ZOOM_STEP = 0.25
const MIN_ZOOM = 0.25
const MAX_ZOOM = 4

export default function MermaidDiagramModal({ isOpen, onClose, code }: MermaidDiagramModalProps) {
  const [copied, setCopied] = useState(false)
  const [scale, setScale] = useState(1)
  const [translate, setTranslate] = useState({ x: 0, y: 0 })
  const [isPanning, setIsPanning] = useState(false)
  const [panStart, setPanStart] = useState({ x: 0, y: 0 })
  const [showSource, setShowSource] = useState(false)
  const viewportRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) {
      setScale(1)
      setTranslate({ x: 0, y: 0 })
      setShowSource(false)
    }
  }, [isOpen])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleZoomIn = () => {
    setScale(prev => Math.min(prev + ZOOM_STEP, MAX_ZOOM))
  }

  const handleZoomOut = () => {
    setScale(prev => Math.max(prev - ZOOM_STEP, MIN_ZOOM))
  }

  const handleResetView = () => {
    setScale(1)
    setTranslate({ x: 0, y: 0 })
  }

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport || !isOpen) return

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
      setScale(prev => Math.min(Math.max(prev + delta, MIN_ZOOM), MAX_ZOOM))
    }

    viewport.addEventListener('wheel', onWheel, { passive: false })
    return () => viewport.removeEventListener('wheel', onWheel)
  }, [isOpen])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    setIsPanning(true)
    setPanStart({ x: e.clientX - translate.x, y: e.clientY - translate.y })
  }, [translate])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return
    setTranslate({
      x: e.clientX - panStart.x,
      y: e.clientY - panStart.y,
    })
  }, [isPanning, panStart])

  const handleMouseUp = useCallback(() => {
    setIsPanning(false)
  }, [])

  const zoomPercent = Math.round(scale * 100)

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Mermaid Diagram" maxWidth="screen" scrollable={false}>
      <div className="flex flex-col h-[70vh]">
        <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-t-lg">
          <div className="flex items-center gap-1">
            <button
              onClick={handleZoomOut}
              disabled={scale <= MIN_ZOOM}
              className="p-1.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Zoom out"
            >
              <MagnifyingGlassMinusIcon className="w-5 h-5" />
            </button>
            <span className="text-xs font-medium text-gray-600 dark:text-gray-400 w-12 text-center tabular-nums">
              {zoomPercent}%
            </span>
            <button
              onClick={handleZoomIn}
              disabled={scale >= MAX_ZOOM}
              className="p-1.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Zoom in"
            >
              <MagnifyingGlassPlusIcon className="w-5 h-5" />
            </button>
            <button
              onClick={handleResetView}
              className="p-1.5 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
              aria-label="Reset view"
            >
              <ArrowsPointingOutIcon className="w-5 h-5" />
            </button>
          </div>
          <span className="text-xs text-gray-500 dark:text-gray-500">
            Scroll to zoom &middot; Drag to pan
          </span>
        </div>

        <div
          ref={viewportRef}
          className={`flex-1 min-h-0 border-x border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-hidden select-none ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <div
            className="w-full h-full flex items-center justify-center [&_svg]:max-w-full [&_svg]:max-h-full [&_svg]:w-full [&_svg]:h-full"
            style={{
              transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
              transformOrigin: 'center center',
            }}
          >
            <MermaidDiagram code={code} className="!p-0 !bg-transparent !rounded-none w-full h-full" />
          </div>
        </div>

        <div className="border border-gray-200 dark:border-gray-700 rounded-b-lg">
          <div className="flex items-center justify-between px-3 py-2">
            <button
              onClick={() => setShowSource(prev => !prev)}
              className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
            >
              <ChevronRightIcon className={`w-4 h-4 transition-transform ${showSource ? 'rotate-90' : ''}`} />
              Source Code
            </button>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-2 py-1 text-xs font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
            >
              {copied ? (
                <>
                  <CheckIcon className="w-4 h-4 text-green-500" />
                  Copied!
                </>
              ) : (
                <>
                  <ClipboardDocumentIcon className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>
          </div>
          {showSource && (
            <div className="max-h-48 overflow-auto border-t border-gray-200 dark:border-gray-700">
              <CodeBlock code={code} language="mermaid" />
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}
