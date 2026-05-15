import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from '../../../test/utils'
import { PlanTab } from '../PlanTab'
import { TaskStatus } from '../../../lib/api'
import type { ImplementationPlanResponse, ImplementationStepResponse } from '../../../lib/api'

vi.mock('../../../lib/api', async () => {
  const actual = await vi.importActual('../../../lib/api')
  return {
    ...actual,
    apiClient: {
      getConversationMessages: vi.fn().mockResolvedValue({ messages: [], context_usage: null }),
      interruptConversation: vi.fn().mockResolvedValue(undefined),
      addImplementationStep: vi.fn().mockResolvedValue(undefined),
      updateImplementationStep: vi.fn().mockResolvedValue(undefined),
    },
  }
})

const makeStep = (overrides: Partial<ImplementationStepResponse> = {}): ImplementationStepResponse => ({
  id: 1,
  step_number: 1,
  title: 'Test step',
  type: 'code_change',
  dependencies: [],
  status: 'pending',
  details: 'Step details',
  outcome: null,
  conversation_id: null,
  started_at: null,
  completed_at: null,
  model_type: null,
  model_display_name: null,
  ...overrides,
})

const makePlan = (steps: ImplementationStepResponse[]): ImplementationPlanResponse => ({
  id: 1,
  task_id: 1,
  overview: null,
  status: 'pending',
  steps,
})

const defaultProps = {
  taskId: 1,
  taskStatus: TaskStatus.PLANNING,
  onPlanUpdated: vi.fn(),
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PlanTab — StepCard model display name', () => {
  it('shows model_display_name as static text for non-pending steps', () => {
    const plan = makePlan([makeStep({ status: 'complete', model_display_name: 'Haiku' })])
    render(<PlanTab {...defaultProps} implementationPlan={plan} />)
    expect(screen.getByText('Haiku')).toBeInTheDocument()
  })

  it('does not render model display name when model_display_name is null on non-pending step', () => {
    const plan = makePlan([makeStep({ status: 'complete', model_display_name: null })])
    render(<PlanTab {...defaultProps} implementationPlan={plan} />)
    expect(screen.queryByText('Haiku')).not.toBeInTheDocument()
    expect(screen.queryByText('Sonnet')).not.toBeInTheDocument()
    expect(screen.queryByText('Opus')).not.toBeInTheDocument()
  })

  it('shows different model names for different non-pending steps', () => {
    const plan = makePlan([
      makeStep({ id: 1, step_number: 1, title: 'Step one', status: 'complete', model_display_name: 'Haiku' }),
      makeStep({ id: 2, step_number: 2, title: 'Step two', type: 'code_review', status: 'complete', model_display_name: 'Sonnet' }),
    ])
    render(<PlanTab {...defaultProps} implementationPlan={plan} />)
    expect(screen.getByText('Haiku')).toBeInTheDocument()
    expect(screen.getByText('Sonnet')).toBeInTheDocument()
  })

  it('shows model select dropdown for pending steps', () => {
    const plan = makePlan([makeStep({ status: 'pending', model_type: 'fast' })])
    render(<PlanTab {...defaultProps} implementationPlan={plan} />)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select).toBeInTheDocument()
    expect(select.value).toBe('fast')
  })

  it('shows disabled placeholder option for pending step with no model_type', () => {
    const plan = makePlan([makeStep({ status: 'pending', model_type: null })])
    render(<PlanTab {...defaultProps} implementationPlan={plan} />)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select).toBeInTheDocument()
    expect(screen.getByText('select model')).toBeInTheDocument()
  })
})
