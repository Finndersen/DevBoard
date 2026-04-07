import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '../../../test/utils'
import ContextUsageDisplay from '../ContextUsageDisplay'
import { useConversationStreamStore } from '../../../stores/conversationStreamStore'
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

describe('ContextUsageDisplay', () => {
  const conversationId = 42

  beforeEach(() => {
    // Clear the store entry between tests
    useConversationStreamStore.setState(state => {
      const next = new Map(state.conversationMessages)
      next.delete(conversationId)
      return { conversationMessages: next }
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
    render(<ContextUsageDisplay conversationId={conversationId} />)
    const el = screen.getByText(/ctx/)
    expect(el.getAttribute('title')).toContain('Input: 400')
    expect(el.getAttribute('title')).toContain('Output: 200')
    expect(el.getAttribute('title')).toContain('Cache read: 50,000')
    expect(el.getAttribute('title')).toContain('Cache write: 2,000')
  })
})
