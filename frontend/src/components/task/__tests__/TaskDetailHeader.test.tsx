import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import { TaskDetailHeader } from '../TaskDetailHeader'
import { TaskStatus } from '../../../lib/api'
import type { Task, TaskGitStatus } from '../../../lib/api'

// Mock the useEditableField hook
vi.mock('../../../hooks/useEditableField', () => ({
  useEditableField: () => ({
    editedValue: 'Test Task',
    isEditing: false,
    setEditedValue: vi.fn(),
    startEditing: vi.fn(),
    cancelEditing: vi.fn(),
    save: vi.fn(),
    saving: false,
  }),
}))

// Mock the CustomFieldsPopover
vi.mock('../../common/CustomFieldsPanel', () => ({
  CustomFieldsPopover: () => null,
}))

const mockTask: Task = {
  id: 1,
  title: 'Test Task',
  status: TaskStatus.PLANNING,
  project_id: 1,
  codebase_id: 1,
  conversation_id: 1,
  created_at: '2026-06-10T00:00:00Z',
  specification_document_id: 1,
  implementation_plan_document_id: null,
  implementation_plan_id: null,
  change_summary_document_id: null,
  custom_fields: null,
  github_pr_number: null,
  available_workflow_actions: [],
}

const mockGitStatus: TaskGitStatus = {
  branch_name: 'task-123-feature',
  branch_exists: true,
  base_branch: 'main',
  commits_ahead: 2,
  commits_behind: 0,
  can_merge: true,
  has_conflicts: false,
  worktree_slot: null,
  worktree_slot_path: null,
  main_repo_is_clean: true,
  main_repo_current_branch: 'main',
  rebase_in_progress: false,
  has_uncommitted_base_overlap: false,
  remote_fetch_failed: false,
  base_has_conflicting_uncommitted: false,
}

const mockProject = { id: 1, name: 'Test Project' }

const defaultProps = {
  task: mockTask,
  project: mockProject,
  titleField: {
    editedValue: 'Test Task',
    isEditing: false,
    setEditedValue: vi.fn(),
    startEditing: vi.fn(),
    cancelEditing: vi.fn(),
    save: vi.fn(),
    saving: false,
  },
  codebases: null,
  selectedCodebase: null,
  gitStatus: mockGitStatus,
  branchStatusLoading: false,
  onCodebaseSelect: vi.fn(),
  onOpenBranchStatusModal: vi.fn(),
  onDeleteTask: vi.fn(),
  deleteLoading: false,
  deleteError: null,
}

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('TaskDetailHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Project breadcrumb', () => {
    it('shows ◆ symbol and project name', () => {
      renderWithRouter(<TaskDetailHeader {...defaultProps} />)
      expect(screen.getByText('◆')).toBeInTheDocument()
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })

    it('project name links to the project', () => {
      renderWithRouter(<TaskDetailHeader {...defaultProps} />)
      const link = screen.getByTitle('Test Project').closest('a')
      expect(link).toHaveAttribute('href', '/projects/1')
    })
  })

  describe('Status badge variant', () => {
    it('renders COMPLETE status with success variant', () => {
      const completeTask = { ...mockTask, status: TaskStatus.COMPLETE }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={completeTask}
        />
      )

      const statusBadge = screen.getByText(TaskStatus.COMPLETE)
      expect(statusBadge).toBeInTheDocument()
      // Check for success variant styling (green colors)
      expect(statusBadge.className).toMatch(/bg-green|text-green/)
    })

    it('renders MERGED status with success variant', () => {
      const mergedTask = { ...mockTask, status: TaskStatus.MERGED }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={mergedTask}
        />
      )

      const statusBadge = screen.getByText(TaskStatus.MERGED)
      expect(statusBadge).toBeInTheDocument()
      // Check for success variant styling (green colors)
      expect(statusBadge.className).toMatch(/bg-green|text-green/)
    })

    it('renders PR_OPEN status with warning variant', () => {
      const prOpenTask = { ...mockTask, status: TaskStatus.PR_OPEN }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={prOpenTask}
        />
      )

      const statusBadge = screen.getByText(TaskStatus.PR_OPEN)
      expect(statusBadge).toBeInTheDocument()
      // Check for warning variant styling (amber/yellow colors)
      expect(statusBadge.className).toMatch(/bg-amber|text-amber|bg-yellow|text-yellow/)
    })

    it('renders PLANNING status with info variant', () => {
      const planningTask = { ...mockTask, status: TaskStatus.PLANNING }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={planningTask}
        />
      )

      const statusBadge = screen.getByText(TaskStatus.PLANNING)
      expect(statusBadge).toBeInTheDocument()
      // Check for info variant styling (blue colors)
      expect(statusBadge.className).toMatch(/bg-blue|text-blue/)
    })
  })

  describe('Branch status button visibility', () => {
    it('shows branch status button for PR_OPEN status when branch_name is present', () => {
      const prOpenTask = { ...mockTask, status: TaskStatus.PR_OPEN }
      const gitStatus = { ...mockGitStatus, branch_name: 'task-123-feature' }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={prOpenTask}
          gitStatus={gitStatus}
        />
      )

      // The branch status button contains a GitBranchIcon SVG and the branch name text
      const branchButton = screen.getByTitle(mockGitStatus.branch_name)
      expect(branchButton).toBeInTheDocument()
    })

    it('hides branch status button for MERGED status even when branch_name is present', () => {
      const mergedTask = { ...mockTask, status: TaskStatus.MERGED }
      const gitStatus = { ...mockGitStatus, branch_name: 'task-123-feature' }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={mergedTask}
          gitStatus={gitStatus}
        />
      )

      // The branch status button should not be present
      const branchButton = screen.queryByTitle(mockGitStatus.branch_name)
      expect(branchButton).not.toBeInTheDocument()
    })

    it('hides branch status button for COMPLETE status even when branch_name is present', () => {
      const completeTask = { ...mockTask, status: TaskStatus.COMPLETE }
      const gitStatus = { ...mockGitStatus, branch_name: 'task-123-feature' }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={completeTask}
          gitStatus={gitStatus}
        />
      )

      // The branch status button should not be present
      const branchButton = screen.queryByTitle(mockGitStatus.branch_name)
      expect(branchButton).not.toBeInTheDocument()
    })

    it('shows branch status button for IMPLEMENTING status when branch_name is present', () => {
      const implementingTask = { ...mockTask, status: TaskStatus.IMPLEMENTING }
      const gitStatus = { ...mockGitStatus, branch_name: 'task-123-feature' }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={implementingTask}
          gitStatus={gitStatus}
        />
      )

      // The branch status button should be present
      const branchButton = screen.getByTitle(mockGitStatus.branch_name)
      expect(branchButton).toBeInTheDocument()
    })

    it('hides branch status button when branch_name is null', () => {
      const prOpenTask = { ...mockTask, status: TaskStatus.PR_OPEN }
      const gitStatus = { ...mockGitStatus, branch_name: '' }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={prOpenTask}
          gitStatus={gitStatus}
        />
      )

      // Query for any element that might be the branch button with empty branch name
      // Since branch_name is empty, the title won't match any branch status
      const allButtons = screen.getAllByRole('button')
      const branchButtons = allButtons.filter(btn =>
        btn.innerHTML.includes('GitBranchIcon') || btn.title.includes('task-')
      )
      expect(branchButtons.length).toBe(0)
    })

    it('hides branch status button when gitStatus is null', () => {
      const prOpenTask = { ...mockTask, status: TaskStatus.PR_OPEN }
      renderWithRouter(
        <TaskDetailHeader
          {...defaultProps}
          task={prOpenTask}
          gitStatus={null}
        />
      )

      // The branch status button should not be present
      const allButtons = screen.getAllByRole('button')
      const branchButtons = allButtons.filter(btn =>
        btn.innerHTML.includes('GitBranchIcon') || btn.title.includes('task-')
      )
      expect(branchButtons.length).toBe(0)
    })
  })
})
