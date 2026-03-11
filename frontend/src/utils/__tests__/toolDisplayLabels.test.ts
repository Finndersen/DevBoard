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
})

describe('relativizePath', () => {
  it('strips main repo prefix when codebaseLocalPath provided', () => {
    expect(
      relativizePath('/Users/dev/projects/DevBoard/backend/file.py', '/Users/dev/projects/DevBoard'),
    ).toBe('backend/file.py')
  })

  it('strips alongside-mode worktree path without codebaseLocalPath', () => {
    expect(
      relativizePath('/Users/dev/projects/DevBoard.worktree-2/backend/file.py'),
    ).toBe('backend/file.py')
  })

  it('strips central-mode worktree path without codebaseLocalPath', () => {
    expect(
      relativizePath('/Users/finn.andersen/.devboard/worktrees/1_DevBoard.worktree-4/backend/file.py'),
    ).toBe('backend/file.py')
  })

  it('strips alongside-mode worktree path even when codebaseLocalPath provided', () => {
    expect(
      relativizePath(
        '/Users/dev/projects/DevBoard.worktree-2/backend/file.py',
        '/Users/dev/projects/DevBoard',
      ),
    ).toBe('backend/file.py')
  })

  it('returns path unchanged when no match', () => {
    expect(relativizePath('/Users/dev/other/file.py')).toBe('/Users/dev/other/file.py')
  })

  it('returns path unchanged when empty', () => {
    expect(relativizePath('')).toBe('')
  })
})
