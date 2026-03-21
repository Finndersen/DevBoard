import { useState, useRef, useEffect, useCallback } from 'react'
import type { RefObject } from 'react'
import { Bars3Icon } from '@heroicons/react/24/outline'
import type { TocHeading } from '../../utils/markdown'

interface TableOfContentsPopoverProps {
  headings: TocHeading[]
  scrollContainerRef: RefObject<HTMLElement | null>
}

const levelPadding: Record<number, string> = {
  1: 'pl-3',
  2: 'pl-3',
  3: 'pl-6',
  4: 'pl-6',
  5: 'pl-9',
  6: 'pl-9',
}

const levelTextSize: Record<number, string> = {
  1: 'text-sm',
  2: 'text-sm',
  3: 'text-xs',
  4: 'text-xs',
  5: 'text-xs',
  6: 'text-xs',
}

export default function TableOfContentsPopover({
  headings,
  scrollContainerRef,
}: TableOfContentsPopoverProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeSlug, setActiveSlug] = useState<string | null>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    if (!isOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  // Active section tracking via IntersectionObserver (only when open)
  useEffect(() => {
    if (!isOpen || !scrollContainerRef.current) return

    const container = scrollContainerRef.current
    const headingElements = headings
      .map((h) => container.querySelector<HTMLElement>(`#${CSS.escape(h.slug)}`))
      .filter(Boolean) as HTMLElement[]

    if (headingElements.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const intersecting = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)

        if (intersecting.length > 0) {
          setActiveSlug(intersecting[0].target.id)
        }
      },
      {
        root: container,
        rootMargin: '0px 0px -70% 0px',
      },
    )

    headingElements.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, headings])

  const handleHeadingClick = useCallback(
    (slug: string) => {
      const container = scrollContainerRef.current
      if (!container) return
      const element = container.querySelector<HTMLElement>(`#${CSS.escape(slug)}`)
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
      setIsOpen(false)
    },
    [scrollContainerRef],
  )

  return (
    <div className="relative" ref={popoverRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-white/[0.08] shadow-sm hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors text-gray-600 dark:text-gray-400"
      >
        <Bars3Icon className="w-3.5 h-3.5" />
        <span>Contents</span>
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-1 w-[230px] max-h-72 overflow-y-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-white/[0.08] rounded-lg shadow-lg z-50 py-1">
          {headings.map((heading) => (
            <button
              key={heading.slug}
              onClick={() => handleHeadingClick(heading.slug)}
              className={`w-full text-left pr-3 py-1.5 ${levelPadding[heading.level]} ${levelTextSize[heading.level]} transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 ${
                activeSlug === heading.slug
                  ? 'text-blue-500 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-l-2 border-blue-500 dark:border-blue-400'
                  : 'text-gray-700 dark:text-gray-300'
              }`}
            >
              {heading.text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
