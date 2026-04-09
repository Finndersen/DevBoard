import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useLogEntries, usePinnedLogEntries } from '../useLogEntries'
import { apiClient } from '../../lib/api'
import type { LogEntry } from '../../lib/api'

vi.mock('../../lib/api', () => ({
  apiClient: {
    getLogEntries: vi.fn(),
  },
}))

const mockGetLogEntries = vi.mocked(apiClient.getLogEntries)

const mockEntries: LogEntry[] = [
  {
    id: 1,
    timestamp: '2024-01-01T00:00:00Z',
    source: 'developer',
    type: 'thought',
    content: 'Test entry',
    metadata: null,
    project_id: null,
    task_id: null,
    status: 'active',
    pinned: false,
  },
]

describe('useLogEntries', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetLogEntries.mockResolvedValue(mockEntries)
  })

  it('fetches log entries on mount', async () => {
    const { result } = renderHook(() => useLogEntries())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual(mockEntries)
    expect(result.current.error).toBeNull()
    expect(mockGetLogEntries).toHaveBeenCalledWith({})
  })

  it('passes filters to the API call', async () => {
    const filters = { project_id: 5, source: 'developer' as const }
    const { result } = renderHook(() => useLogEntries(filters))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(mockGetLogEntries).toHaveBeenCalledWith(filters)
  })

  it('refetches when filters change', async () => {
    let filters = { project_id: 1 }
    const { result, rerender } = renderHook(() => useLogEntries(filters))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    const callCount = mockGetLogEntries.mock.calls.length

    filters = { project_id: 2 }
    rerender()

    await waitFor(() => {
      expect(mockGetLogEntries.mock.calls.length).toBeGreaterThan(callCount)
    })

    expect(mockGetLogEntries).toHaveBeenCalledWith({ project_id: 2 })
  })

  it('exposes refetch function', async () => {
    const { result } = renderHook(() => useLogEntries())

    await waitFor(() => expect(result.current.loading).toBe(false))

    const callsBefore = mockGetLogEntries.mock.calls.length
    await act(async () => {
      await result.current.refetch()
    })

    expect(mockGetLogEntries.mock.calls.length).toBeGreaterThan(callsBefore)
  })

  it('handles errors', async () => {
    mockGetLogEntries.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useLogEntries())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Network error')
    expect(result.current.data).toBeNull()
  })
})

describe('usePinnedLogEntries', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetLogEntries.mockResolvedValue(mockEntries)
  })

  it('forces pinned=true and status=active', async () => {
    const { result } = renderHook(() => usePinnedLogEntries())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(mockGetLogEntries).toHaveBeenCalledWith(
      expect.objectContaining({ pinned: true, status: 'active' })
    )
  })

  it('merges caller filters with pinned overrides', async () => {
    const { result } = renderHook(() => usePinnedLogEntries({ project_id: 3 }))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(mockGetLogEntries).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 3, pinned: true, status: 'active' })
    )
  })
})
