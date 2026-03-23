// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { getToolDisplayLabel, relativizePath } from '../toolDisplayLabels'

describe('getToolDisplayLabel', () => {
  describe('Skill', () => {
    it('returns skill arg as details when present', () => {
      expect(getToolDisplayLabel('Skill', { skill: 'commit' })).toEqual({
        toolName: 'Skill',
        details: 'commit',
      })
    })

    it('returns toolName only when no args', () => {
      expect(getToolDisplayLabel('Skill', null)).toEqual({ toolName: 'Skill' })
    })
  })

  describe('ToolSearch', () => {
    it('returns query arg as details when present', () => {
      expect(getToolDisplayLabel('ToolSearch', { query: 'slack message' })).toEqual({
        toolName: 'ToolSearch',
        details: 'slack message',
      })
    })

    it('returns toolName only when no args', () => {
      expect(getToolDisplayLabel('ToolSearch', null)).toEqual({ toolName: 'ToolSearch' })
    })
  })

  describe('TaskOutput', () => {
    it('returns task_id arg as details when present', () => {
      expect(getToolDisplayLabel('TaskOutput', { task_id: 'abc123' })).toEqual({
        toolName: 'TaskOutput',
        details: 'abc123',
      })
    })

    it('returns toolName only when no args', () => {
      expect(getToolDisplayLabel('TaskOutput', null)).toEqual({ toolName: 'TaskOutput' })
    })
  })

  describe('edit_task', () => {
    it('returns title as details when only title is updated', () => {
      expect(getToolDisplayLabel('edit_task', { title: 'New title' })).toEqual({
        toolName: 'edit_task',
        details: 'title',
      })
    })

    it('returns specification as details when only specification_content is updated', () => {
      expect(getToolDisplayLabel('edit_task', { specification_content: 'New spec' })).toEqual({
        toolName: 'edit_task',
        details: 'specification',
      })
    })

    it('returns both fields as details when title and specification_content are updated', () => {
      expect(getToolDisplayLabel('edit_task', { title: 'New title', specification_content: 'New spec' })).toEqual({
        toolName: 'edit_task',
        details: 'title, specification',
      })
    })

    it('returns custom fields as details when only custom_fields is updated', () => {
      expect(getToolDisplayLabel('edit_task', { custom_fields: { priority: 'high' } })).toEqual({
        toolName: 'edit_task',
        details: 'custom fields',
      })
    })

    it('returns all fields when all are updated', () => {
      expect(getToolDisplayLabel('edit_task', { title: 'T', specification_content: 'S', custom_fields: { k: 'v' } })).toEqual({
        toolName: 'edit_task',
        details: 'title, specification, custom fields',
      })
    })

    it('returns toolName only when no updatable args', () => {
      expect(getToolDisplayLabel('edit_task', null)).toEqual({ toolName: 'edit_task' })
    })
  })
})

describe('relativizePath', () => {
  it('strips main repo prefix when workingDir provided', () => {
    expect(
      relativizePath('/Users/dev/projects/DevBoard/backend/file.py', '/Users/dev/projects/DevBoard'),
    ).toBe('backend/file.py')
  })

  it('strips alongside-mode worktree path without workingDir', () => {
    expect(
      relativizePath('/Users/dev/projects/DevBoard.worktree-2/backend/file.py'),
    ).toBe('backend/file.py')
  })

  it('strips central-mode worktree path without workingDir', () => {
    expect(
      relativizePath('/Users/finn.andersen/.devboard/worktrees/1_DevBoard.worktree-4/backend/file.py'),
    ).toBe('backend/file.py')
  })

  it('strips alongside-mode worktree path even when workingDir provided', () => {
    expect(
      relativizePath(
        '/Users/dev/projects/DevBoard.worktree-2/backend/file.py',
        '/Users/dev/projects/DevBoard',
      ),
    ).toBe('backend/file.py')
  })

  it('strips hex UUID worktree paths (alongside mode)', () => {
    expect(
      relativizePath('/Users/dev/projects/DevBoard.worktree-564afd1/backend/file.py'),
    ).toBe('backend/file.py')
  })

  it('strips hex UUID worktree paths (central mode)', () => {
    expect(
      relativizePath('/Users/finn/.devboard/worktrees/DevBoard.worktree-564afd1/src/file.ts'),
    ).toBe('src/file.ts')
  })

  it('strips worktree path when workingDir is the worktree path (exact match takes priority)', () => {
    expect(
      relativizePath(
        '/Users/finn/.devboard/worktrees/DevBoard.worktree-564afd1/src/file.ts',
        '/Users/finn/.devboard/worktrees/DevBoard.worktree-564afd1',
      ),
    ).toBe('src/file.ts')
  })

  it('returns path unchanged when no match', () => {
    expect(relativizePath('/Users/dev/other/file.py')).toBe('/Users/dev/other/file.py')
  })

  it('returns path unchanged when empty', () => {
    expect(relativizePath('')).toBe('')
  })
})
