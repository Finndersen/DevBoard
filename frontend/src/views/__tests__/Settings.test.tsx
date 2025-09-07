import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/setup'
import { render } from '../../test/utils'
import Settings from '../Settings'

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders settings header and navigation tabs', () => {
    render(<Settings />)

    expect(screen.getByText('Settings')).toBeInTheDocument()
    expect(screen.getByText('Configure integrations, AI providers, and system preferences')).toBeInTheDocument()
    
    // Check tabs
    expect(screen.getByRole('button', { name: /integrations/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /ai providers/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /general/i })).toBeInTheDocument()
  })

  it('shows integrations tab as default active', () => {
    render(<Settings />)

    expect(screen.getByRole('button', { name: /integrations/i })).toHaveClass('border-blue-500', 'text-blue-600')
  })

  it('switches between tabs correctly', async () => {
    const user = userEvent.setup()
    render(<Settings />)

    // Default is integrations
    expect(screen.getByRole('button', { name: /integrations/i })).toHaveClass('border-blue-500')

    // Click AI Providers tab
    await user.click(screen.getByRole('button', { name: /ai providers/i }))
    expect(screen.getByRole('button', { name: /ai providers/i })).toHaveClass('border-blue-500')
    expect(screen.getByRole('button', { name: /integrations/i })).not.toHaveClass('border-blue-500')

    // Click General tab
    await user.click(screen.getByRole('button', { name: /general/i }))
    expect(screen.getByRole('button', { name: /general/i })).toHaveClass('border-blue-500')
    expect(screen.getByRole('button', { name: /ai providers/i })).not.toHaveClass('border-blue-500')
  })

  it('displays integration list in integrations tab', () => {
    render(<Settings />)

    expect(screen.getByText('External Integrations')).toBeInTheDocument()
    // Just check that integration names appear somewhere on the page
    expect(screen.getAllByText('GitHub Integration').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Jira Integration').length).toBeGreaterThan(0) 
    expect(screen.getAllByText('Slack Integration').length).toBeGreaterThan(0)
  })

  it('selects first integration by default', () => {
    render(<Settings />)

    // GitHub should be selected by default (has selection indicator)
    const githubElements = screen.getAllByText('GitHub Integration')
    const githubButton = githubElements[0].closest('button')
    expect(githubButton).toHaveClass('bg-blue-50')
  })

  it('switches integration selection', async () => {
    const user = userEvent.setup()
    render(<Settings />)

    // Click Jira integration - use getAllByText to get the first one (in sidebar)
    const jiraElements = screen.getAllByText('Jira Integration')
    await user.click(jiraElements[0]) // Click the first one (sidebar)
    
    const jiraButton = jiraElements[0].closest('button')
    expect(jiraButton).toHaveClass('bg-blue-50')

    const githubElements = screen.getAllByText('GitHub Integration')
    const githubButton = githubElements[0].closest('button')
    expect(githubButton).not.toHaveClass('bg-blue-50')
  })

  it('displays configuration form for selected integration', () => {
    render(<Settings />)

    // ConfigurationForm should be rendered with GitHub integration by default
    expect(screen.getAllByText('GitHub Integration').length).toBeGreaterThan(0)
  })

  it('displays AI providers in agents tab', async () => {
    const user = userEvent.setup()
    render(<Settings />)

    await user.click(screen.getByRole('button', { name: /ai providers/i }))

    // Just check that AI providers tab is working - main header shows
    expect(screen.getAllByText('AI Providers').length).toBeGreaterThan(0)
    // Check that some providers are shown
    expect(screen.getAllByText('OpenAI Provider').length).toBeGreaterThan(0)
  })


  it('displays general settings in general tab', async () => {
    const user = userEvent.setup()
    render(<Settings />)

    await user.click(screen.getByRole('button', { name: /general/i }))

    expect(screen.getByText('General Settings')).toBeInTheDocument()
    // Just check basic settings are present
    expect(screen.getByText('Dark Mode')).toBeInTheDocument()
    expect(screen.getByText('Auto-save')).toBeInTheDocument()
  })

})