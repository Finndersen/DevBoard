import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useApi } from '../useApi'

describe('useApi', () => {
  it('fetches data immediately by default', async () => {
    const mockData = { id: 1, name: 'Test' }
    const apiCall = vi.fn().mockResolvedValue(mockData)

    const { result } = renderHook(() => useApi(apiCall))

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual(mockData)
    expect(result.current.error).toBeNull()
    expect(apiCall).toHaveBeenCalledTimes(1)
  })

  it('does not fetch immediately when immediate is false', () => {
    const apiCall = vi.fn().mockResolvedValue({ id: 1 })

    const { result } = renderHook(() => useApi(apiCall, { immediate: false }))

    expect(result.current.loading).toBe(false)
    expect(result.current.data).toBeNull()
    expect(apiCall).not.toHaveBeenCalled()
  })

  it('handles errors', async () => {
    const apiCall = vi.fn().mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useApi(apiCall))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toBeNull()
    expect(result.current.error).toBe('Network error')
  })

  it('deduplicates concurrent refetch calls and queues a follow-up', async () => {
    const resolvers: Array<(value: { id: number }) => void> = []
    const apiCall = vi.fn().mockImplementation(() =>
      new Promise(resolve => { resolvers.push(resolve) })
    )

    const { result } = renderHook(() => useApi(apiCall, { immediate: false }))

    // Fire two refetch calls concurrently — only one API call starts immediately
    act(() => {
      result.current.refetch()
      result.current.refetch()
    })
    expect(apiCall).toHaveBeenCalledTimes(1)

    // Resolve the first request — the pending flag should trigger a follow-up call
    await act(async () => {
      resolvers[0]!({ id: 1 })
    })

    // A second API call should now be in-flight (the pending refetch)
    await waitFor(() => {
      expect(apiCall).toHaveBeenCalledTimes(2)
    })

    // Resolve the follow-up request
    await act(async () => {
      resolvers[1]!({ id: 2 })
    })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    // Data reflects the follow-up (latest) response
    expect(result.current.data).toEqual({ id: 2 })
  })

  it('allows refetch after previous request completes', async () => {
    let callCount = 0
    const apiCall = vi.fn().mockImplementation(() => {
      callCount++
      return Promise.resolve({ id: callCount })
    })

    const { result } = renderHook(() => useApi(apiCall, { immediate: false }))

    // First refetch
    await act(async () => {
      await result.current.refetch()
    })

    expect(apiCall).toHaveBeenCalledTimes(1)
    expect(result.current.data).toEqual({ id: 1 })

    // Second refetch after first completes - should work
    await act(async () => {
      await result.current.refetch()
    })

    expect(apiCall).toHaveBeenCalledTimes(2)
    expect(result.current.data).toEqual({ id: 2 })
  })

  it('resets in-flight flag after error', async () => {
    let callCount = 0
    const apiCall = vi.fn().mockImplementation(() => {
      callCount++
      if (callCount === 1) return Promise.reject(new Error('fail'))
      return Promise.resolve({ id: callCount })
    })

    const { result } = renderHook(() => useApi(apiCall, { immediate: false }))

    // First call fails
    await act(async () => {
      await result.current.refetch()
    })

    expect(result.current.error).toBe('fail')

    // Second call should work (in-flight flag was reset)
    await act(async () => {
      await result.current.refetch()
    })

    expect(result.current.data).toEqual({ id: 2 })
    expect(result.current.error).toBeNull()
  })

  it('preserves existing data when refetch fails', async () => {
    let callCount = 0
    const apiCall = vi.fn().mockImplementation(() => {
      callCount++
      if (callCount === 1) return Promise.resolve({ id: 1, name: 'Original' })
      return Promise.reject(new Error('Transient network error'))
    })

    const { result } = renderHook(() => useApi(apiCall))

    // Initial load succeeds
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
    expect(result.current.data).toEqual({ id: 1, name: 'Original' })
    expect(result.current.error).toBeNull()

    // Refetch fails - data should be preserved
    await act(async () => {
      await result.current.refetch()
    })

    expect(result.current.data).toEqual({ id: 1, name: 'Original' })
    expect(result.current.error).toBe('Transient network error')
    expect(result.current.loading).toBe(false)
  })

  it('allows setting data directly via setData', async () => {
    const apiCall = vi.fn().mockResolvedValue({ id: 1 })

    const { result } = renderHook(() => useApi(apiCall, { immediate: false }))

    act(() => {
      result.current.setData({ id: 42 })
    })

    expect(result.current.data).toEqual({ id: 42 })
    expect(result.current.loading).toBe(false)
  })
})
