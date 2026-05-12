import { useCallback, useEffect, useState } from 'react'

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)

  useEffect(() => {
    const mediaQuery = window.matchMedia(query)
    setMatches(mediaQuery.matches)

    const handler = (event: MediaQueryListEvent) => {
      setMatches(event.matches)
    }

    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [query])

  return matches
}

export function useIsBelow2xl(): boolean {
  return !useMediaQuery('(min-width: 1536px)')
}

/**
 * Returns [isNarrow, callbackRef]. Attach the callbackRef to the container
 * element. Uses ResizeObserver so it responds to container size changes
 * (e.g. sidebar collapse/expand) rather than viewport width.
 */
export function useIsNarrowContainer(breakpoint: number = 1280): [boolean, (node: HTMLElement | null) => void] {
  const [isNarrow, setIsNarrow] = useState(false)
  const [element, setElement] = useState<HTMLElement | null>(null)

  const callbackRef = useCallback((node: HTMLElement | null) => {
    setElement(node)
    // Synchronous initial measurement to avoid layout flash
    if (node) {
      setIsNarrow(node.getBoundingClientRect().width < breakpoint)
    }
  }, [breakpoint])

  useEffect(() => {
    if (!element) return

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0
      setIsNarrow(width < breakpoint)
    })

    observer.observe(element)
    return () => observer.disconnect()
  }, [element, breakpoint])

  return [isNarrow, callbackRef]
}
