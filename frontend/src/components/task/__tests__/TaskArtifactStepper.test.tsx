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

  describe('finalise step', () => {
    it('does not show finalise step for statuses before MERGED', () => {
      for (const status of [TaskStatus.PLANNING, TaskStatus.IMPLEMENTING, TaskStatus.PR_OPEN]) {
        const { unmount } = render(
          <TaskArtifactStepper
            {...defaultProps}
            taskStatus={status}
            hasSpecification={true}
            hasPlan={status !== TaskStatus.PLANNING}
            hasChanges={status === TaskStatus.IMPLEMENTING || status === TaskStatus.PR_OPEN}
            hasPR={status === TaskStatus.PR_OPEN}
          />
        )
        expect(screen.queryByRole('button', { name: /finalise/i })).not.toBeInTheDocument()
        unmount()
      }
    })

    it('shows finalise step as active when task is MERGED', () => {
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

      const finaliseStep = screen.getByRole('button', { name: /finalise/i })
      expect(finaliseStep).toBeInTheDocument()
      // Active step should have the active circle indicator (not a checkmark)
      const circleIndicator = finaliseStep.querySelector('.rounded-full')
      expect(circleIndicator).toBeInTheDocument()
    })

    it('shows finalise step as done (complete) when task is COMPLETE', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          taskStatus={TaskStatus.COMPLETE}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
          hasPR={true}
          hasSummary={true}
        />
      )

      const finaliseStep = screen.getByRole('button', { name: /finalise/i })
      expect(finaliseStep).toBeInTheDocument()
    })

    it('highlights finalise step when it is the activeStep in MERGED state', () => {
      render(
        <TaskArtifactStepper
          {...defaultProps}
          activeStep="finalise"
          taskStatus={TaskStatus.MERGED}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
        />
      )

      const finaliseStep = screen.getByRole('button', { name: /finalise/i })
      expect(finaliseStep).toHaveClass('bg-blue-900/30', 'border-blue-500', 'text-blue-400')
    })

    it('calls onStepClick with finalise when finalise step is clicked in MERGED state', () => {
      const onStepClick = vi.fn()
      render(
        <TaskArtifactStepper
          {...defaultProps}
          onStepClick={onStepClick}
          taskStatus={TaskStatus.MERGED}
          hasSpecification={true}
          hasPlan={true}
          hasChanges={true}
        />
      )

      const finaliseStep = screen.getByRole('button', { name: /finalise/i })
      fireEvent.click(finaliseStep)
      expect(onStepClick).toHaveBeenCalledWith('finalise')
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
