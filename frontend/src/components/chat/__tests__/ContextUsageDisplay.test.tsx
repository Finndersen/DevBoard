import { describe, it, expect, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { render } from '../../../test/utils'
import ContextUsageDisplay, { ContextUsageBadge } from '../ContextUsageDisplay'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
import { useConversationStore } from '../../../stores/conversationStore'
import type { ContextUsage } from '../../../lib/api'

function seedUsage(conversationId: number, usage: ContextUsage | null | undefined) {
  useConversationStreamStore.setState(state => {
    const existing = state.conversationMessages.get(conversationId)
    const next = new Map(state.conversationMessages)
    next.set(conversationId, {
      messages: existing?.messages ?? [],
      historyLoaded: existing?.historyLoaded ?? true,
      contextUsage: usage,
    })
    return { conversationMessages: next }
  })
}

function seedConversation(conversationId: number, autoRefocus = true) {
  useConversationStore.setState(state => {
    const next = new Map(state.conversations)
    next.set(conversationId, {
      id: conversationId,
      messages: [],
      draftMessage: '',
      scrollPosition: 0,
      isTyping: false,
      lastActivity: new Date(),
      autoRefocus,
    })
    return { conversations: next }
  })
}

describe('ContextUsageDisplay', () => {
  const conversationId = 42

  beforeEach(() => {
    useConversationStreamStore.setState(state => {
      const next = new Map(state.conversationMessages)
      next.delete(conversationId)
      return { conversationMessages: next }
    })
    useConversationStore.setState(state => {
      const next = new Map(state.conversations)
      next.delete(conversationId)
      return { conversations: next }
    })
  })

  it('renders nothing when no usage data is available', () => {
    const { container } = render(<ContextUsageDisplay conversationId={conversationId} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when contextUsage is null', () => {
    seedUsage(conversationId, null)
    const { container } = render(<ContextUsageDisplay conversationId={conversationId} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders formatted token count and cache percentage', () => {
    seedUsage(conversationId, {
      input_tokens: 400,
      output_tokens: 200,
      cache_read_tokens: 50000,
      cache_write_tokens: 2000,
      cost_usd: null,
    })
    seedConversation(conversationId)
    render(<ContextUsageDisplay conversationId={conversationId} />)
    // total = 50000 + 2000 + 400 = 52400 → 52.4K
    // cachePercent = round(50000 / 52400 * 100) = 95
    expect(screen.getByText('52.4K ctx · 95% cached')).toBeTruthy()
  })

  it('shows 0% cached when cache_read_tokens is 0', () => {
    seedUsage(conversationId, {
      input_tokens: 1000,
      output_tokens: 100,
      cache_read_tokens: 0,
      cache_write_tokens: 500,
      cost_usd: null,
    })
    seedConversation(conversationId)
    render(<ContextUsageDisplay conversationId={conversationId} />)
    // total = 0 + 500 + 1000 = 1500 → 1.5K
    // cachePercent = 0
    expect(screen.getByText('1.5K ctx · 0% cached')).toBeTruthy()
  })

  it('formats millions correctly', () => {
    seedUsage(conversationId, {
      input_tokens: 100000,
      output_tokens: 5000,
      cache_read_tokens: 800000,
      cache_write_tokens: 200000,
      cost_usd: 0.05,
    })
    seedConversation(conversationId)
    render(<ContextUsageDisplay conversationId={conversationId} />)
    // total = 800000 + 200000 + 100000 = 1100000 → 1.1M
    // cachePercent = round(800000 / 1100000 * 100) = 73
    expect(screen.getByText('1.1M ctx · 73% cached')).toBeTruthy()
  })

  it('includes token breakdown in title attribute', () => {
    seedUsage(conversationId, {
      input_tokens: 400,
      output_tokens: 200,
      cache_read_tokens: 50000,
      cache_write_tokens: 2000,
      cost_usd: null,
    })
    seedConversation(conversationId)
    const { container } = render(<ContextUsageDisplay conversationId={conversationId} />)
    // The outer span on ContextUsageBadge holds the title attribute
    const el = container.querySelector('[title]')!
    expect(el.getAttribute('title')).toContain('Input: 400')
    expect(el.getAttribute('title')).toContain('Output: 200')
    expect(el.getAttribute('title')).toContain('Cache read: 50,000')
    expect(el.getAttribute('title')).toContain('Cache write: 2,000')
  })

  describe('auto-refocus toggle', () => {
    it('renders toggle button when context usage is available', () => {
      seedUsage(conversationId, {
        input_tokens: 1000,
        output_tokens: 100,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
      })
      seedConversation(conversationId, true)
      render(<ContextUsageDisplay conversationId={conversationId} />)
      expect(screen.getByTestId('auto-refocus-toggle')).toBeTruthy()
    })

    it('toggles auto-refocus off when clicked while on', () => {
      seedUsage(conversationId, {
        input_tokens: 1000,
        output_tokens: 100,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
      })
      seedConversation(conversationId, true)
      render(<ContextUsageDisplay conversationId={conversationId} />)
      const toggle = screen.getByTestId('auto-refocus-toggle')
      expect(toggle.getAttribute('aria-label')).toBe('Auto-refocus on')
      fireEvent.click(toggle)
      expect(useConversationStore.getState().conversations.get(conversationId)?.autoRefocus).toBe(false)
    })

    it('toggles auto-refocus on when clicked while off', () => {
      seedUsage(conversationId, {
        input_tokens: 1000,
        output_tokens: 100,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
      })
      seedConversation(conversationId, false)
      render(<ContextUsageDisplay conversationId={conversationId} />)
      const toggle = screen.getByTestId('auto-refocus-toggle')
      expect(toggle.getAttribute('aria-label')).toBe('Auto-refocus off')
      fireEvent.click(toggle)
      expect(useConversationStore.getState().conversations.get(conversationId)?.autoRefocus).toBe(true)
    })
  })
})

describe('ContextUsageBadge — context window utilization', () => {
  it('does not show utilization when context_window is null', () => {
    const { queryByTestId } = render(
      <ContextUsageBadge contextUsage={{
        input_tokens: 50000,
        output_tokens: 1000,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
        context_window: null,
      }} />
    )
    expect(queryByTestId('utilization-percent')).toBeNull()
  })

  it('does not show utilization when context_window is undefined', () => {
    const { queryByTestId } = render(
      <ContextUsageBadge contextUsage={{
        input_tokens: 50000,
        output_tokens: 1000,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
      }} />
    )
    expect(queryByTestId('utilization-percent')).toBeNull()
  })

  it('shows utilization percentage when context_window is provided', () => {
    render(
      <ContextUsageBadge contextUsage={{
        input_tokens: 50000,
        output_tokens: 1000,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
        context_window: 200000,
      }} />
    )
    // 50000 / 200000 = 25%
    expect(screen.getByTestId('utilization-percent').textContent).toBe('25% ctx')
  })

  it('shows warning state when utilization is at or above 70%', () => {
    render(
      <ContextUsageBadge contextUsage={{
        input_tokens: 140000,
        output_tokens: 5000,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
        context_window: 200000,
      }} />
    )
    // 140000 / 200000 = 70% — exactly at threshold
    const utilizationEl = screen.getByTestId('utilization-percent')
    expect(utilizationEl.textContent).toBe('70% ctx')
    // Warning color class should be applied
    const progressBar = screen.getByRole('progressbar')
    expect(progressBar.firstElementChild?.className).toContain('amber')
  })

  it('shows normal state when utilization is below 70%', () => {
    render(
      <ContextUsageBadge contextUsage={{
        input_tokens: 100000,
        output_tokens: 5000,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
        context_window: 200000,
      }} />
    )
    // 100000 / 200000 = 50% — below threshold
    const progressBar = screen.getByRole('progressbar')
    expect(progressBar.firstElementChild?.className).not.toContain('amber')
    expect(progressBar.firstElementChild?.className).toContain('blue')
  })

  it('includes utilization and context_window in tooltip', () => {
    const { container } = render(
      <ContextUsageBadge contextUsage={{
        input_tokens: 100000,
        output_tokens: 5000,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        cost_usd: null,
        context_window: 200000,
      }} />
    )
    // The outer span carries the title attribute
    const badge = container.querySelector('[title]')!
    expect(badge.getAttribute('title')).toContain('Context window: 200,000')
    expect(badge.getAttribute('title')).toContain('Utilization: 50%')
  })
})
