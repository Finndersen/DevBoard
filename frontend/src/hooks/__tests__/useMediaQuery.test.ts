import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMediaQuery, useIsBelow2xl, useIsNarrowContainer } from '../useMediaQuery'

describe('useMediaQuery', () => {
  let listeners: Map<string, (event: MediaQueryListEvent) => void>

  beforeEach(() => {
    listeners = new Map()
    vi.mocked(window.matchMedia).mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_event: string, handler: (event: MediaQueryListEvent) => void) => {
        listeners.set(query, handler)
      }),
      removeEventListener: vi.fn((_event: string, _handler: (event: MediaQueryListEvent) => void) => {
        listeners.delete(query)
      }),
      dispatchEvent: vi.fn(),
    }))
  })

  it('returns false when query does not match', () => {
    const { result } = renderHook(() => useMediaQuery('(min-width: 1536px)'))
    expect(result.current).toBe(false)
  })

  it('returns true when query matches', () => {
    vi.mocked(window.matchMedia).mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_event: string, handler: (event: MediaQueryListEvent) => void) => {
        listeners.set(query, handler)
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))

    const { result } = renderHook(() => useMediaQuery('(min-width: 1536px)'))
    expect(result.current).toBe(true)
  })

  it('updates when media query changes', () => {
    const { result } = renderHook(() => useMediaQuery('(min-width: 1536px)'))
    expect(result.current).toBe(false)

    act(() => {
      const handler = listeners.get('(min-width: 1536px)')
      handler?.({ matches: true } as MediaQueryListEvent)
    })

    expect(result.current).toBe(true)
  })

  it('cleans up listener on unmount', () => {
    const removeEventListener = vi.fn()
    vi.mocked(window.matchMedia).mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener,
      dispatchEvent: vi.fn(),
    }))

    const { unmount } = renderHook(() => useMediaQuery('(min-width: 1536px)'))
    unmount()

    expect(removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  })
})

describe('useIsBelow2xl', () => {
  let listeners: Map<string, (event: MediaQueryListEvent) => void>

  beforeEach(() => {
    listeners = new Map()
    vi.mocked(window.matchMedia).mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_event: string, handler: (event: MediaQueryListEvent) => void) => {
        listeners.set(query, handler)
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  })

  it('returns true when viewport is below 1536px', () => {
    const { result } = renderHook(() => useIsBelow2xl())
    expect(result.current).toBe(true)
  })

  it('returns false when viewport is at or above 1536px', () => {
    vi.mocked(window.matchMedia).mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))

    const { result } = renderHook(() => useIsBelow2xl())
    expect(result.current).toBe(false)
  })
})

describe('useIsNarrowContainer', () => {
  let observeCallback: ResizeObserverCallback
  let mockDisconnect: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockDisconnect = vi.fn()
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: ResizeObserverCallback) {
        observeCallback = callback
      }
      observe = vi.fn()
      unobserve = vi.fn()
      disconnect = mockDisconnect
    })
  })

  it('returns false initially before element is attached', () => {
    const { result } = renderHook(() => useIsNarrowContainer())
    const [isNarrow] = result.current
    expect(isNarrow).toBe(false)
  })

  it('returns true when container width is below default breakpoint', () => {
    const { result } = renderHook(() => useIsNarrowContainer())

    // Simulate attaching the ref to an element
    act(() => {
      const [, ref] = result.current
      ref(document.createElement('div'))
    })

    act(() => {
      observeCallback([{ contentRect: { width: 900 } } as ResizeObserverEntry], {} as ResizeObserver)
    })

    expect(result.current[0]).toBe(true)
  })

  it('returns false when container width is at or above default breakpoint', () => {
    const { result } = renderHook(() => useIsNarrowContainer())

    act(() => {
      const [, ref] = result.current
      ref(document.createElement('div'))
    })

    act(() => {
      observeCallback([{ contentRect: { width: 1200 } } as ResizeObserverEntry], {} as ResizeObserver)
    })

    expect(result.current[0]).toBe(false)
  })

  it('respects custom breakpoint', () => {
    const { result } = renderHook(() => useIsNarrowContainer(800))

    act(() => {
      const [, ref] = result.current
      ref(document.createElement('div'))
    })

    act(() => {
      observeCallback([{ contentRect: { width: 750 } } as ResizeObserverEntry], {} as ResizeObserver)
    })

    expect(result.current[0]).toBe(true)
  })

  it('disconnects observer on unmount', () => {
    const { result, unmount } = renderHook(() => useIsNarrowContainer())

    act(() => {
      const [, ref] = result.current
      ref(document.createElement('div'))
    })

    unmount()
    expect(mockDisconnect).toHaveBeenCalled()
  })
})
