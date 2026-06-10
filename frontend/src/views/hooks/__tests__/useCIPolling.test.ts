import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { formatCIFailureMessage, useCIPolling } from '../useCIPolling'
import { apiClient, TaskStatus } from '../../../lib/api'
import type { Task, PRDetailResponse, PRCheckItem } from '../../../lib/api'

vi.mock('../../../lib/api', async () => {
  const actual = await vi.importActual('../../../lib/api')
  return {
    ...actual,
    apiClient: {
      getPRDetail: vi.fn(),
    },
  }
})

describe('formatCIFailureMessage', () => {
  it('formats check names with descriptions', () => {
    const checks: PRCheckItem[] = [
      { name: 'tests', state: 'FAILURE', description: 'Unit tests failed' },
      { name: 'lint', state: 'FAILURE', description: null },
    ]
    const message = formatCIFailureMessage(checks, 42)
    expect(message).toContain('PR #42')
    expect(message).toContain('- tests: Unit tests failed')
    expect(message).toContain('- lint')
    expect(message).not.toContain('- lint:')
  })

  it('includes instruction to fix failures', () => {
    const checks: PRCheckItem[] = [{ name: 'test', state: 'FAILURE', description: null }]
    const message = formatCIFailureMessage(checks, 1)
    expect(message).toContain('Please investigate and fix these CI failures')
  })
})

describe('useCIPolling', () => {
  let fakePRDetail: PRDetailResponse
  let mockTask: Task

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    localStorage.clear()

    fakePRDetail = {
      ci_status: 'failure',
      checks: [
        { name: 'tests', state: 'SUCCESS', description: 'Tests passed' },
        { name: 'lint', state: 'FAILURE', description: 'Lint errors' },
      ],
      reviews: [],
      review_comment_count: 0,
    }

    mockTask = {
      id: 1,
      title: 'Test Task',
      status: TaskStatus.PR_OPEN,
      project_id: 1,
      codebase_id: 42,
      conversation_id: 1,
      created_at: '2024-01-01T00:00:00Z',
      specification_document_id: 1,
      implementation_plan_document_id: null,
      implementation_plan_id: null,
      change_summary_document_id: null,
      custom_fields: null,
      github_pr_number: 100,
      available_workflow_actions: [],
    }

    vi.mocked(apiClient.getPRDetail).mockResolvedValue(fakePRDetail)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('initializes with auto-resolve false when not in localStorage', () => {
    const { result } = renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: vi.fn(),
      })
    )

    expect(result.current.autoResolve).toBe(false)
  })

  it('reads auto-resolve from localStorage on mount', () => {
    localStorage.setItem('ci_auto_resolve_1', 'true')

    const { result } = renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: vi.fn(),
      })
    )

    expect(result.current.autoResolve).toBe(true)
  })

  it('persists auto-resolve to localStorage when toggled', () => {
    const { result } = renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: vi.fn(),
      })
    )

    act(() => {
      result.current.setAutoResolve(true)
    })

    expect(localStorage.getItem('ci_auto_resolve_1')).toBe('true')

    act(() => {
      result.current.setAutoResolve(false)
    })

    expect(localStorage.getItem('ci_auto_resolve_1')).toBe('false')
  })

  it('does not poll when task is not PR_OPEN', () => {
    const task: Task = { ...mockTask, status: TaskStatus.IMPLEMENTING }

    renderHook(() =>
      useCIPolling({
        task,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: vi.fn(),
      })
    )

    vi.advanceTimersByTime(30_000)

    expect(apiClient.getPRDetail).not.toHaveBeenCalled()
  })

  it('does not poll when task is null', () => {
    renderHook(() =>
      useCIPolling({
        task: null,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: vi.fn(),
      })
    )

    vi.advanceTimersByTime(30_000)

    expect(apiClient.getPRDetail).not.toHaveBeenCalled()
  })

  it('does not poll when no github_pr_number', () => {
    const task = { ...mockTask, github_pr_number: null }

    renderHook(() =>
      useCIPolling({
        task,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: vi.fn(),
      })
    )

    vi.advanceTimersByTime(30_000)

    expect(apiClient.getPRDetail).not.toHaveBeenCalled()
  })

  it('polls on 30-second interval when conditions met', async () => {
    const onUpdate = vi.fn()

    renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: onUpdate,
        onReportIssues: vi.fn(),
      })
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(apiClient.getPRDetail).toHaveBeenCalledTimes(1)
    expect(onUpdate).toHaveBeenCalledWith(fakePRDetail)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(apiClient.getPRDetail).toHaveBeenCalledTimes(2)
  })

  it('clears polling when task status changes away from PR_OPEN', () => {
    const { rerender } = renderHook(
      ({ task }: { task: Task | null }) =>
        useCIPolling({
          task,
        prDetail: null,
          isConversationStreaming: false,
          onPRDetailUpdate: vi.fn(),
          onReportIssues: vi.fn(),
        }),
      { initialProps: { task: mockTask } }
    )

    vi.advanceTimersByTime(30_000)
    expect(apiClient.getPRDetail).toHaveBeenCalledTimes(1)

    vi.clearAllMocks()

    const mergedTask: Task = { ...mockTask, status: TaskStatus.MERGED }
    rerender({ task: mergedTask })

    vi.advanceTimersByTime(30_000)

    expect(apiClient.getPRDetail).not.toHaveBeenCalled()
  })

  it('auto-reports failing checks when auto-resolve is enabled', async () => {
    const onReport = vi.fn()

    localStorage.setItem('ci_auto_resolve_1', 'true')

    renderHook(
      ({ task }: { task: Task | null }) =>
        useCIPolling({
          task,
        prDetail: null,
          isConversationStreaming: false,
          onPRDetailUpdate: vi.fn(),
          onReportIssues: onReport,
        }),
      { initialProps: { task: mockTask } }
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(onReport).toHaveBeenCalled()
    const message = onReport.mock.calls[0][0]
    expect(message).toContain('PR #100')
    expect(message).toContain('lint')
  })

  it('does not auto-report when auto-resolve is disabled', async () => {
    const onReport = vi.fn()

    renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: onReport,
      })
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(apiClient.getPRDetail).toHaveBeenCalled()
    expect(onReport).not.toHaveBeenCalled()
  })

  it('does not auto-report when conversation is streaming', async () => {
    localStorage.setItem('ci_auto_resolve_1', 'true')

    const onReport = vi.fn()

    renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: true,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: onReport,
      })
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(apiClient.getPRDetail).toHaveBeenCalled()
    expect(onReport).not.toHaveBeenCalled()
  })

  it('does not auto-report when no failing checks', async () => {
    localStorage.setItem('ci_auto_resolve_1', 'true')

    const onReport = vi.fn()

    vi.mocked(apiClient.getPRDetail).mockResolvedValue({
      ci_status: 'success',
      checks: [
        { name: 'tests', state: 'SUCCESS', description: null },
        { name: 'lint', state: 'SUCCESS', description: null },
      ],
      reviews: [],
      review_comment_count: 0,
    })

    renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: onReport,
      })
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(apiClient.getPRDetail).toHaveBeenCalled()
    expect(onReport).not.toHaveBeenCalled()
  })

  it('de-duplicates reports for same failure set', async () => {
    localStorage.setItem('ci_auto_resolve_1', 'true')

    const onReport = vi.fn()

    renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: onReport,
      })
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(onReport).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(apiClient.getPRDetail).toHaveBeenCalledTimes(2)
    expect(onReport).toHaveBeenCalledTimes(1)
  })

  it('reports again when failure set changes', async () => {
    localStorage.setItem('ci_auto_resolve_1', 'true')

    const onReport = vi.fn()

    renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: onReport,
      })
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(onReport).toHaveBeenCalledTimes(1)

    vi.mocked(apiClient.getPRDetail).mockResolvedValueOnce({
      ci_status: 'failure',
      checks: [
        { name: 'tests', state: 'FAILURE', description: 'Different failure' },
        { name: 'build', state: 'FAILURE', description: null },
      ],
      reviews: [],
      review_comment_count: 0,
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })

    expect(onReport).toHaveBeenCalledTimes(2)
  })

  it('resets dedup key when task ID changes so same failures are re-reported', async () => {
    localStorage.setItem('ci_auto_resolve_1', 'true')
    localStorage.setItem('ci_auto_resolve_2', 'true')

    const onReport = vi.fn()

    const { rerender } = renderHook(
      ({ task }: { task: Task | null }) =>
        useCIPolling({
          task,
          prDetail: null,
          isConversationStreaming: false,
          onPRDetailUpdate: vi.fn(),
          onReportIssues: onReport,
        }),
      { initialProps: { task: mockTask } }
    )

    // First poll reports the failure
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })
    expect(onReport).toHaveBeenCalledTimes(1)

    // Switch to a different task (same failing checks)
    const newTask: Task = { ...mockTask, id: 2 }
    rerender({ task: newTask })

    vi.mocked(apiClient.getPRDetail).mockResolvedValue(fakePRDetail)

    // After task ID changes, dedup key is reset — same failures are reported again
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000)
    })
    expect(onReport).toHaveBeenCalledTimes(2)
  })

  it('clears polling on unmount', () => {
    const { unmount } = renderHook(() =>
      useCIPolling({
        task: mockTask,
        prDetail: null,
        isConversationStreaming: false,
        onPRDetailUpdate: vi.fn(),
        onReportIssues: vi.fn(),
      })
    )

    vi.advanceTimersByTime(30_000)
    expect(apiClient.getPRDetail).toHaveBeenCalled()

    vi.clearAllMocks()
    unmount()

    vi.advanceTimersByTime(30_000)

    expect(apiClient.getPRDetail).not.toHaveBeenCalled()
  })
})
