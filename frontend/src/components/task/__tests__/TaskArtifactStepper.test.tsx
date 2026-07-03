import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { TaskArtifactStepper } from '../TaskArtifactStepper'
import { TaskStatus } from '../../../lib/api'
import type { TaskArtifactStepperProps } from '../TaskArtifactStepper'

const defaultProps: TaskArtifactStepperProps = {
  activeStep: 'specification',
  onStepClick: vi.fn(),
  taskStatus: TaskStatus.PLANNING,
  hasSpecification: true,
  hasPlan: false,
  hasChanges: false,
  hasPR: false,
  hasSummary: false,
}

describe('TaskArtifactStepper', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('step visibility — only current and previous steps shown', () => {
    it('shows only spec when task is in planning with no plan', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.PLANNING}
          hasSpecification={true}
          hasPlan={false}
        />
      )

      expect(screen.getByRole('button', { name: /spec/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /^plan$/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /changes/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /pr/i })).not.toBeInTheDocument()
    })

    it('shows spec and plan when task is planning with plan', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.PLANNING}
          hasSpecification={true}
          hasPlan={true}
        />
      )

      expect(screen.getByRole('button', { name: /spec/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /plan/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /changes/i })).not.toBeInTheDocument()
    })

    it('shows spec, plan, changes when implementing', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.IMPLEMENTING}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
        />
      )

      expect(screen.getByRole('button', { name: /spec/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /plan/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /changes/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /pr/i })).not.toBeInTheDocument()
    })

    it('shows all steps including PR when PR is open', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.PR_OPEN}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
          hasPR={true}
        />
      )

      expect(screen.getByRole('button', { name: /spec/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /plan/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /changes/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /pr/i })).toBeInTheDocument()
    })
  })

  describe('selected step highlighting', () => {
    it('highlights the selected step with blue styling', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          activeStep="specification"
          taskStatus={TaskStatus.IMPLEMENTING}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
        />
      )

      const specStep = screen.getByRole('button', { name: /spec/i })
      expect(specStep).toHaveClass('bg-blue-900/30', 'border-blue-500', 'text-blue-400')

      // Other steps should not have selected styling
      const planStep = screen.getByRole('button', { name: /plan/i })
      expect(planStep).not.toHaveClass('bg-blue-900/30')
      expect(planStep).toHaveClass('text-gray-400')
    })

    it('highlights changes step when selected', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          activeStep="changes"
          taskStatus={TaskStatus.IMPLEMENTING}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
        />
      )

      const changesStep = screen.getByRole('button', { name: /changes/i })
      expect(changesStep).toHaveClass('bg-blue-900/30', 'border-blue-500', 'text-blue-400')

      const specStep = screen.getByRole('button', { name: /spec/i })
      expect(specStep).not.toHaveClass('bg-blue-900/30')
    })
  })

  describe('status indicators', () => {
    it('shows checkmark for completed steps', () => {
      const { container } = render(
        <TaskArtifactStepper
          {...defaultProps}
          activeStep="changes"
          taskStatus={TaskStatus.IMPLEMENTING}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
        />
      )

      // Complete steps (spec, plan) should have solid check circle icons
      const checkIcons = container.querySelectorAll('[data-slot="icon"]')
      expect(checkIcons.length).toBeGreaterThan(0)
    })

    it('shows spinning icon for executing plan', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.PLANNING}
          hasSpecification={true}
          hasPlan={true}
          planStatus="executing"
        />
      )

      const planStep = screen.getByRole('button', { name: /plan/i })
      const spinningIcon = planStep.querySelector('.animate-spin')
      expect(spinningIcon).toBeInTheDocument()
    })

    it('shows X icon for failed plan', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.PLANNING}
          hasSpecification={true}
          hasPlan={true}
          planStatus="failed"
        />
      )

      const planStep = screen.getByRole('button', { name: /plan/i })
      const xIcon = planStep.querySelector('.text-red-500')
      expect(xIcon).toBeInTheDocument()
    })

    it('shows file count badge for changes', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.IMPLEMENTING}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
          changeCount={5}
        />
      )

      const changesStep = screen.getByRole('button', { name: /changes/i })
      expect(changesStep).toHaveTextContent('5')
    })

    it('shows PR status indicators', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.PR_OPEN}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
          hasPR={true}
          prStatus={{
            merged: false,
            mergeable_state: 'CLEAN',
            ci_status: 'SUCCESS',
            review_decision: 'APPROVED'
          }}
        />
      )

      const prStep = screen.getByRole('button', { name: /pr/i })
      expect(prStep).toBeInTheDocument()
    })
  })

  describe('click handlers', () => {
    const onStepClick = vi.fn()

    it('calls onStepClick when clickable step is clicked', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          onStepClick={onStepClick}
          hasSpecification={true}
        />
      )

      const specStep = screen.getByRole('button', { name: /spec/i })
      fireEvent.click(specStep)

      expect(onStepClick).toHaveBeenCalledWith('specification')
    })

    it('calls onStepClick for summary step in COMPLETE tasks', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          onStepClick={onStepClick}
          taskStatus={TaskStatus.COMPLETE}
          hasSpecification={true}
          hasSummary={true}
        />
      )

      const summaryStep = screen.getByRole('button', { name: /summary/i })
      fireEvent.click(summaryStep)

      expect(onStepClick).toHaveBeenCalledWith('summary')
    })
  })

  describe('MERGED state', () => {
    it('shows spec, plan, change summary, and PR steps (all complete) when task is MERGED', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.MERGED}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
          hasPR={true}
        />
      )

      expect(screen.getByRole('button', { name: /spec/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /plan/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /change summary/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /^changes$/i })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /pr/i })).toBeInTheDocument()
    })
  })

  describe('summary handling', () => {
    it('shows summary step for COMPLETE tasks with hasSummary', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.COMPLETE}
          hasSpecification={true}
          hasSummary={true}
        />
      )

      const summaryStep = screen.getByRole('button', { name: /summary/i })
      expect(summaryStep).toBeInTheDocument()
    })

    it('does not show summary step for non-COMPLETE tasks', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.IMPLEMENTING}
          hasSpecification={true}
          hasSummary={true}
        />
      )

      const summaryStep = screen.queryByRole('button', { name: /summary/i })
      expect(summaryStep).not.toBeInTheDocument()
    })

    it('highlights summary step when activeStep is summary', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          activeStep="summary"
          taskStatus={TaskStatus.COMPLETE}
          hasSpecification={true}
          hasSummary={true}
        />
      )

      const summaryStep = screen.getByRole('button', { name: /summary/i })
      expect(summaryStep).toHaveClass('text-blue-400')
    })
  })
})
