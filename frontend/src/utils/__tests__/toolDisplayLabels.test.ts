import { describe, it, expect } from 'vitest'
import { getToolDisplayLabel } from '../toolDisplayLabels'

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
