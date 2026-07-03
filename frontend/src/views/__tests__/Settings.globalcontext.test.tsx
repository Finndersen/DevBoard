import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { render } from '../../test/utils'
import { server } from '../../test/setup'
import type { GlobalContextResponse } from '../../lib/api'
import Settings from '../Settings'

const mockGlobalContextWithContent: GlobalContextResponse = {
  content: '# Domain Context\n\nThis is a SaaS platform for developer tooling.',
  content_hash: 'abc123',
  updated_at: '2024-01-01T00:00:00Z',
}

describe('Settings — Global Context tab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('"Global Context" tab is visible in navigation', () => {
    render(<Settings />)
    expect(screen.getByText('Global Context')).toBeInTheDocument()
  })

  it('renders global context editor after switching to the tab', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('*/api/global-context', () => HttpResponse.json(mockGlobalContextWithContent))
    )

    render(<Settings />)

    await user.click(screen.getByText('Global Context'))

    await waitFor(() => {
      expect(screen.getByText(/Global context is shared with all agents/)).toBeInTheDocument()
    })
  })

  it('displays content from GET /api/global-context in the editor', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('*/api/global-context', () => HttpResponse.json(mockGlobalContextWithContent))
    )

    render(<Settings />)
    await user.click(screen.getByText('Global Context'))

    await waitFor(() => {
      // MarkdownDocumentEditor renders markdown — the heading text should appear
      expect(screen.getByText('Domain Context')).toBeInTheDocument()
    })
  })

  it('shows empty state when no global context content exists', async () => {
    const user = userEvent.setup()

    render(<Settings />)
    await user.click(screen.getByText('Global Context'))

    await waitFor(() => {
      expect(screen.getByText(/No global context defined/)).toBeInTheDocument()
    })
  })

  it('saves updated content via PUT /api/global-context', async () => {
    const user = userEvent.setup()
    const updatedContent = 'Updated global context content'
    let capturedBody: { content: string } | null = null

    server.use(
      http.get('*/api/global-context', () => HttpResponse.json(mockGlobalContextWithContent)),
      http.put('*/api/global-context', async ({ request }) => {
        capturedBody = await request.json() as { content: string }
        return HttpResponse.json({
          content: capturedBody.content,
          content_hash: 'newhash',
          updated_at: new Date().toISOString(),
        })
      })
    )

    render(<Settings />)
    await user.click(screen.getByText('Global Context'))

    // Wait for editor to load then click Edit
    await waitFor(() => {
      expect(screen.getByText('Edit')).toBeInTheDocument()
    })
    await user.click(screen.getByText('Edit'))

    // Clear textarea and type new content
    const textarea = screen.getByRole('textbox')
    await user.clear(textarea)
    await user.type(textarea, updatedContent)

    await user.click(screen.getByText('Save'))

    await waitFor(() => {
      expect(capturedBody).toEqual({ content: updatedContent })
    })
  })

  it('does not fetch global context API until the tab is activated', async () => {
    const user = userEvent.setup()
    let fetchCount = 0

    server.use(
      http.get('*/api/global-context', () => {
        fetchCount++
        return HttpResponse.json({ content: '', content_hash: 'hash', updated_at: '2024-01-01T00:00:00Z' })
      })
    )

    render(<Settings />)

    // Initially on integrations tab — global context should NOT have been fetched
    expect(fetchCount).toBe(0)

    // Switch to global context tab
    await user.click(screen.getByText('Global Context'))

    await waitFor(() => {
      expect(fetchCount).toBe(1)
    })
  })
})
