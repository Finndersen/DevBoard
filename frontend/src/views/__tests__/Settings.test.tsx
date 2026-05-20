import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '../../test/utils'
import Settings from '../Settings'

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders settings header and tab navigation', () => {
    render(<Settings />)

    expect(screen.getByText('Settings')).toBeInTheDocument()

    // Check tab navigation
    expect(screen.getByText('Integrations')).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('General')).toBeInTheDocument()
  })

  it('shows integrations tab as default active', () => {
    render(<Settings />)

    // Integrations tab should be active by default (has blue styling)
    const integrationsTab = screen.getByText('Integrations')
    expect(integrationsTab.closest('button')).toHaveClass('border-blue-500', 'text-blue-600')
  })

  it('can switch between tabs', async () => {
    const user = userEvent.setup()
    render(<Settings />)

    // Click on Agents tab
    const agentsTab = screen.getByText('Agents')
    await user.click(agentsTab)
    
    // Should show agents content description text (appears in both role list and config panel)
    await waitFor(() => {
      expect(screen.getAllByText('Answers questions about projects and helps with specifications').length).toBeGreaterThan(0)
    })

    // Click on General tab
    const generalTab = screen.getByText('General')
    await user.click(generalTab)
    
    // Should show general settings
    expect(screen.getByText('General Settings')).toBeInTheDocument()
    expect(screen.getByText('Dark Mode')).toBeInTheDocument()
  })

  it('displays integration list when on integrations tab', async () => {
    render(<Settings />)

    // Should show "All Integrations" section
    expect(screen.getByText('All Integrations')).toBeInTheDocument()
    
    // Wait for integrations to load and appear
    await waitFor(() => {
      expect(screen.getByText('GitHub')).toBeInTheDocument()
    })
    
    expect(screen.getByText('Jira')).toBeInTheDocument() 
    expect(screen.getByText('Slack')).toBeInTheDocument()
    expect(screen.getByText('OpenAI')).toBeInTheDocument()
    expect(screen.getByText('Anthropic')).toBeInTheDocument()
    expect(screen.getByText('Google')).toBeInTheDocument()
  })

  it('shows configuration form when integration selected', async () => {
    render(<Settings />)

    // Wait for the configuration to load
    await waitFor(() => {
      expect(screen.getByText('GitHub')).toBeInTheDocument()
    })
    
    // Should show a configuration form area
    await waitFor(() => {
      const configSection = screen.getByText('GitHub API token')
      expect(configSection).toBeInTheDocument()
    })
  })

  it('handles integration selection', async () => {
    const user = userEvent.setup()
    render(<Settings />)

    // Wait for integrations to load
    await waitFor(() => {
      expect(screen.getByText('GitHub')).toBeInTheDocument()
    })

    // Click on different integrations
    const jiraButton = screen.getByText('Jira').closest('button')
    await user.click(jiraButton!)

    // Should still be able to interact with the interface
    expect(jiraButton).toBeInTheDocument()
  })

  it('renders Claude Code Engine section in agents tab', async () => {
    const user = userEvent.setup()
    render(<Settings />)

    // Click on Agents tab
    const agentsTab = screen.getByText('Agents')
    await user.click(agentsTab)

    // Should display Claude Code Engine section with compact layout
    await waitFor(() => {
      expect(screen.getByText('Claude Code Engine')).toBeInTheDocument()
      expect(screen.getByText('Client Mode')).toBeInTheDocument()
    })
  })

})