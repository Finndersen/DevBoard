import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AgentRoleConfigPanel } from '../AgentRoleConfigPanel'
import { apiClient } from '../../../lib/api'

vi.mock('../../../lib/api')

const mockEngines = [
  {
    engine: 'claude_code',
    display_name: 'Claude Code',
    description: 'Claude Code with tool use',
    is_available: true,
    requires_model_selection: true,
    unavailable_reason: null,
  },
  {
    engine: 'openai',
    display_name: 'OpenAI',
    description: 'OpenAI engine',
    is_available: true,
    requires_model_selection: true,
    unavailable_reason: null,
  },
  {
    engine: 'anthropic',
    display_name: 'Anthropic',
    description: 'Anthropic direct API',
    is_available: true,
    requires_model_selection: true,
    unavailable_reason: null,
  },
]

const mockModels = {
  models_by_engine: {
    claude_code: [
      { id: 'claude-opus', name: 'Claude Opus', model_type: 'advanced' },
      { id: 'claude-sonnet', name: 'Claude Sonnet', model_type: 'standard' },
    ],
    openai: [
      { id: 'gpt-4', name: 'GPT-4', model_type: 'advanced' },
    ],
    anthropic: [
      { id: 'claude-opus-api', name: 'Claude Opus (API)', model_type: 'advanced' },
    ],
  },
}

describe('AgentRoleConfigPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Global Default option', () => {
    it('renders "Global Default (Claude Code)" as first option when role has no engine set', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: null,
          model: null,
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)

      render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine="claude_code"
        />
      )

      // Wait for component to load
      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Open engine dropdown
      const engineButton = screen.getByRole('button', { name: /Global Default \(Claude Code\)/ })
      fireEvent.click(engineButton)

      // Wait for dropdown to open
      await waitFor(() => {
        expect(screen.getByText('Use the global default engine')).toBeInTheDocument()
      })

      // Find the Global Default option in the dropdown and verify it's highlighted
      const globalDefaultInDropdown = screen.getByText('Use the global default engine').closest('button')
      expect(globalDefaultInDropdown).toHaveClass('bg-blue-50')
      expect(globalDefaultInDropdown).toHaveTextContent('Global Default (Claude Code)')
      // Note: "Claude Code" is resolved from available_engines display_name, not passed directly
    })

    it('displays "Global Default" without parenthetical when globalDefaultEngine is null', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: null,
          model: null,
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)

      render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine={null}
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Check that button shows just "Global Default" without parentheses
      expect(screen.getByRole('button', { name: /^Global Default$/ })).toBeInTheDocument()
    })

    it('selects "Global Default" option when no engine is configured', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: null,
          model: null,
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)

      render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine="claude_code"
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Open engine dropdown
      const engineButton = screen.getByRole('button', { name: /Global Default/ })
      fireEvent.click(engineButton)

      // Verify the Global Default option is highlighted
      const globalDefaultOption = screen.getAllByText(/Global Default/)[1] // The one in dropdown
      expect(globalDefaultOption.closest('button')).toHaveClass('bg-blue-50')
    })
  })

  describe('Engine selection', () => {
    it('sends engine: null in API request when "Global Default" is selected', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: 'claude_code',
          model: { id: 'claude-opus', name: 'Claude Opus' },
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      const updatedConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: null,
          model: null,
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)
      vi.mocked(apiClient.updateAgentConfiguration).mockResolvedValue(updatedConfig)

      render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine="claude_code"
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Open engine dropdown
      const engineButton = screen.getByRole('button', { name: /Claude Code/ })
      fireEvent.click(engineButton)

      // Click on Global Default option
      const globalDefaultOption = screen.getByText('Use the global default engine')
      fireEvent.click(globalDefaultOption)

      // Verify API was called with engine: null
      await waitFor(() => {
        expect(apiClient.updateAgentConfiguration).toHaveBeenCalledWith(
          'project_qa',
          expect.objectContaining({
            engine: null,
            model_id: null,
          })
        )
      })
    })

    it('sends specific engine value when a specific engine is selected', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: null,
          model: null,
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      const updatedConfig = {
        config: {
          engine: 'openai',
          stored_engine: 'openai',
          model: { id: 'gpt-4', name: 'GPT-4' },
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)
      vi.mocked(apiClient.updateAgentConfiguration).mockResolvedValue(updatedConfig)

      render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine="claude_code"
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Open engine dropdown
      const engineButton = screen.getByRole('button', { name: /Global Default/ })
      fireEvent.click(engineButton)

      // Click on OpenAI option
      const openaiOption = screen.getByText('OpenAI')
      fireEvent.click(openaiOption)

      // Verify API was called with specific engine
      await waitFor(() => {
        expect(apiClient.updateAgentConfiguration).toHaveBeenCalledWith(
          'project_qa',
          expect.objectContaining({
            engine: 'openai',
            model_id: 'gpt-4',
          })
        )
      })
    })
  })

  describe('Model dropdown behavior with Global Default', () => {
    it('disables model dropdown when Global Default engine is selected', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: null,
          model: null,
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)

      const { container } = render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine="claude_code"
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Find the model dropdown button by searching for the label "Model" and getting the button sibling
      const labels = container.querySelectorAll('label')
      const modelLabel = Array.from(labels).find(label => label.textContent === 'Model')
      const modelDropdownContainer = modelLabel?.closest('div')
      const modelButton = modelDropdownContainer?.querySelector('button')

      // Verify it's disabled
      expect(modelButton).toBeDisabled()
    })

    it('enables model dropdown when a specific engine is selected', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: 'claude_code',
          model: { id: 'claude-opus', name: 'Claude Opus' },
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)

      const { container } = render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine="claude_code"
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Find the model dropdown button by searching for the label "Model" and getting the button sibling
      const labels = container.querySelectorAll('label')
      const modelLabel = Array.from(labels).find(label => label.textContent === 'Model')
      const modelDropdownContainer = modelLabel?.closest('div')
      const modelButton = modelDropdownContainer?.querySelector('button')

      // Verify it's enabled (not disabled)
      expect(modelButton).not.toBeDisabled()
    })
  })

  describe('Custom instructions with Global Default', () => {
    it('saves custom instructions with null engine when Global Default is selected', async () => {
      const mockConfig = {
        config: {
          engine: 'claude_code',
          stored_engine: null,
          model: null,
        },
        available_engines: mockEngines,
        custom_instructions: '',
        enabled_mcp_tools: [],
        model_type_display_names: {},
      }

      const updatedConfig = {
        ...mockConfig,
        custom_instructions: 'Test instructions',
      }

      vi.mocked(apiClient.getAgentConfiguration).mockResolvedValue(mockConfig)
      vi.mocked(apiClient.getAvailableModelsByEngine).mockResolvedValue(mockModels)
      vi.mocked(apiClient.updateAgentConfiguration).mockResolvedValue(updatedConfig)

      render(
        <AgentRoleConfigPanel
          agentRole="project_qa"
          agentName="Project Q&A"
          agentDescription="Reviews project context and answers questions"
          globalDefaultEngine="claude_code"
        />
      )

      await waitFor(() => {
        expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
      })

      // Find and fill the custom instructions textarea
      const textarea = screen.getByPlaceholderText(/Enter custom instructions/)
      fireEvent.change(textarea, { target: { value: 'Test instructions' } })

      // Click save button
      const saveButton = screen.getByRole('button', { name: /Save/ })
      fireEvent.click(saveButton)

      // Verify API was called with null engine
      await waitFor(() => {
        expect(apiClient.updateAgentConfiguration).toHaveBeenCalledWith(
          'project_qa',
          expect.objectContaining({
            engine: null,
            custom_instructions: 'Test instructions',
          })
        )
      })
    })
  })
})
