import '@testing-library/jest-dom'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import React from 'react'

// Only setup MSW and browser mocks in browser environment
if (typeof window !== 'undefined' && typeof navigator !== 'undefined') {
  // Mock localStorage before importing MSW
  const localStorageMock = {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    key: vi.fn(() => null),
    length: 0,
  }

  Object.defineProperty(globalThis, 'localStorage', {
    writable: true,
    value: localStorageMock,
  })

  import('msw/node').then(({ setupServer }) => {
    import('./mocks/handlers').then(({ handlers }) => {
      const server = setupServer(...handlers)

      // Establish API mocking before all tests
      beforeAll(() => {
        server.listen({ onUnhandledRequest: 'error' })
      })

      // Reset any request handlers that we may add during the tests,
      // so they don't affect other tests
      afterEach(() => {
        server.resetHandlers()
      })

      // Clean up after the tests are finished
      afterAll(() => {
        server.close()
      })
    })
  })

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(), // deprecated
      removeListener: vi.fn(), // deprecated
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })

  globalThis.IntersectionObserver = class IntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof IntersectionObserver

  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver

  vi.mock('react-syntax-highlighter', () => ({
    Prism: ({ children }: { children: string }) => React.createElement('pre', null, children),
    Light: ({ children }: { children: string }) => React.createElement('pre', null, children),
  }))

  vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
    oneDark: {},
    oneLight: {},
  }))
}
