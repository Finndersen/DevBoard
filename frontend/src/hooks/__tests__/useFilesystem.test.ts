import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useListDirectory } from '../useFilesystem'
import { apiClient } from '../../lib/api'

// Mock the API client
vi.mock('../../lib/api', () => ({
  apiClient: {
    listDirectory: vi.fn(),
  },
}))

describe('useListDirectory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with null data and not loading', () => {
    const { result } = renderHook(() => useListDirectory())

    expect(result.current.data).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('fetches directory listing successfully', async () => {
    const mockResponse = {
      current_path: '/home/user',
      parent_path: '/home',
      directories: ['Documents', 'Downloads'],
    }

    vi.mocked(apiClient.listDirectory).mockResolvedValue(mockResponse)

    const { result } = renderHook(() => useListDirectory())

    await act(async () => {
      await result.current.listDirectory('/home/user')
    })

    await waitFor(() => {
      expect(result.current.data).toEqual(mockResponse)
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })
  })

  it('fetches home directory when no path provided', async () => {
    const mockResponse = {
      current_path: '/home/user',
      parent_path: '/home',
      directories: ['Documents'],
    }

    vi.mocked(apiClient.listDirectory).mockResolvedValue(mockResponse)

    const { result } = renderHook(() => useListDirectory())

    await act(async () => {
      await result.current.listDirectory()
    })

    expect(apiClient.listDirectory).toHaveBeenCalledWith(undefined)
  })

  it('handles API errors', async () => {
    vi.mocked(apiClient.listDirectory).mockRejectedValue(new Error('Not found'))

    const { result } = renderHook(() => useListDirectory())

    await act(async () => {
      try {
        await result.current.listDirectory('/invalid')
      } catch {
        // Expected to throw
      }
    })

    expect(result.current.error).toBe('Not found')
    expect(result.current.loading).toBe(false)
  })

  it('sets loading state during fetch', async () => {
    let resolvePromise: (value: unknown) => void
    const promise = new Promise((resolve) => {
      resolvePromise = resolve
    })

    vi.mocked(apiClient.listDirectory).mockReturnValue(promise as never)

    const { result } = renderHook(() => useListDirectory())

    act(() => {
      result.current.listDirectory('/test')
    })

    expect(result.current.loading).toBe(true)

    await act(async () => {
      resolvePromise!({
        current_path: '/test',
        parent_path: '/',
        directories: [],
      })
    })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
  })
})
