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

  it('deduplicates concurrent refetch calls', async () => {
    let resolveCall: (value: { id: number }) => void
    const apiCall = vi.fn().mockImplementation(() =>
      new Promise(resolve => { resolveCall = resolve })
    )

    const { result } = renderHook(() => useApi(apiCall, { immediate: false }))

    // Fire two refetch calls concurrently
    act(() => {
      result.current.refetch()
      result.current.refetch()
    })

    // Only one API call should have been made
    expect(apiCall).toHaveBeenCalledTimes(1)

    // Resolve the in-flight request
    await act(async () => {
      resolveCall!({ id: 1 })
    })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual({ id: 1 })
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
