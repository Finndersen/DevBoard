import { diffWordsWithSpace, diffChars, diffLines } from 'diff'
import type { DocumentEdit } from './toolTypeUtils'

export interface HighlightedChange {
  type: 'added' | 'removed' | 'unchanged'
  value: string
}

export interface InlineHighlight {
  text: string
  changes: HighlightedChange[]
}

export interface DocumentComparison {
  beforeText: string
  afterText: string
  beforeLines: string[]
  afterLines: string[]
}

/**
 * Generate a unified diff from individual find/replace edits
 */
export function generateUnifiedDiff(edits: DocumentEdit[]): string {
  if (!edits || edits.length === 0) {
    return ''
  }

  let unifiedDiff = ''
  
  edits.forEach((edit, index) => {
    const changes = diffLines(edit.old_string, edit.new_string, { newlineIsToken: true })

    // Add header for each edit
    unifiedDiff += `@@ Edit ${index + 1}: Find and Replace @@\n`
    
    changes.forEach(change => {
      const prefix = change.added ? '+' : change.removed ? '-' : ' '
      const lines = change.value.split('\n')
      
      lines.forEach((line, lineIndex) => {
        // Skip empty last line if it's just from splitting
        if (lineIndex === lines.length - 1 && line === '') return
        unifiedDiff += `${prefix}${line}\n`
      })
    })
    
    if (index < edits.length - 1) {
      unifiedDiff += '\n' // Add spacing between edits
    }
  })

  return unifiedDiff
}

/**
 * Create inline highlighting for find/replace text showing character-level changes
 */
export function createInlineHighlight(oldText: string, newText: string): InlineHighlight {
  // Use word-level diffing for better readability
  const changes = diffWordsWithSpace(oldText, newText)
  
  const highlightedChanges: HighlightedChange[] = changes.map(change => ({
    type: change.added ? 'added' : change.removed ? 'removed' : 'unchanged',
    value: change.value
  }))

  return {
    text: newText,
    changes: highlightedChanges
  }
}

/**
 * Create character-level highlighting for more granular diff display
 */
export function createCharacterHighlight(oldText: string, newText: string): InlineHighlight {
  const changes = diffChars(oldText, newText)
  
  const highlightedChanges: HighlightedChange[] = changes.map(change => ({
    type: change.added ? 'added' : change.removed ? 'removed' : 'unchanged',
    value: change.value
  }))

  return {
    text: newText,
    changes: highlightedChanges
  }
}

/**
 * Apply multiple edits to a document and return before/after comparison
 */
export function createDocumentComparison(originalDocument: string, edits: DocumentEdit[]): DocumentComparison {
  if (!edits || edits.length === 0) {
    return {
      beforeText: originalDocument,
      afterText: originalDocument,
      beforeLines: originalDocument.split('\n'),
      afterLines: originalDocument.split('\n')
    }
  }

  let modifiedDocument = originalDocument

  // Apply edits in order
  edits.forEach(edit => {
    modifiedDocument = modifiedDocument.replace(edit.old_string, edit.new_string)
  })

  return {
    beforeText: originalDocument,
    afterText: modifiedDocument,
    beforeLines: originalDocument.split('\n'),
    afterLines: modifiedDocument.split('\n')
  }
}

/**
 * Calculate diff statistics for a set of edits
 */
export interface DiffStats {
  editsCount: number
  charactersAdded: number
  charactersRemoved: number
  wordsAdded: number
  wordsRemoved: number
  linesAdded: number
  linesRemoved: number
}

export function calculateDiffStats(edits: DocumentEdit[]): DiffStats {
  if (!edits || edits.length === 0) {
    return {
      editsCount: 0,
      charactersAdded: 0,
      charactersRemoved: 0,
      wordsAdded: 0,
      wordsRemoved: 0,
      linesAdded: 0,
      linesRemoved: 0
    }
  }

  let charactersAdded = 0
  let charactersRemoved = 0
  let wordsAdded = 0
  let wordsRemoved = 0
  let linesAdded = 0
  let linesRemoved = 0

  edits.forEach(edit => {
    const oldLength = edit.old_string.length
    const newLength = edit.new_string.length

    if (newLength > oldLength) {
      charactersAdded += newLength - oldLength
    } else {
      charactersRemoved += oldLength - newLength
    }

    const oldWords = edit.old_string.split(/\s+/).filter(w => w.length > 0)
    const newWords = edit.new_string.split(/\s+/).filter(w => w.length > 0)

    if (newWords.length > oldWords.length) {
      wordsAdded += newWords.length - oldWords.length
    } else {
      wordsRemoved += oldWords.length - newWords.length
    }

    const oldLines = edit.old_string.split('\n')
    const newLines = edit.new_string.split('\n')

    if (newLines.length > oldLines.length) {
      linesAdded += newLines.length - oldLines.length
    } else {
      linesRemoved += oldLines.length - newLines.length
    }
  })

  return {
    editsCount: edits.length,
    charactersAdded,
    charactersRemoved,
    wordsAdded,
    wordsRemoved,
    linesAdded,
    linesRemoved
  }
}

/**
 * Format diff statistics for display
 */
export function formatDiffStats(stats: DiffStats): string {
  const parts: string[] = []
  
  if (stats.editsCount > 0) {
    parts.push(`${stats.editsCount} edit${stats.editsCount !== 1 ? 's' : ''}`)
  }
  
  if (stats.charactersAdded > 0 || stats.charactersRemoved > 0) {
    const netChange = stats.charactersAdded - stats.charactersRemoved
    if (netChange > 0) {
      parts.push(`+${netChange} characters`)
    } else if (netChange < 0) {
      parts.push(`${netChange} characters`)
    }
  }
  
  if (stats.linesAdded > 0 || stats.linesRemoved > 0) {
    if (stats.linesAdded > 0) parts.push(`+${stats.linesAdded} lines`)
    if (stats.linesRemoved > 0) parts.push(`-${stats.linesRemoved} lines`)
  }
  
  return parts.join(', ') || 'No changes'
}

/**
 * Syntax highlighting for unified diff format
 */
export function highlightUnifiedDiff(diffText: string): Array<{ line: string; type: 'header' | 'added' | 'removed' | 'context' }> {
  const lines = diffText.split('\n')
  
  return lines.map(line => {
    if (line.startsWith('@@')) {
      return { line, type: 'header' as const }
    } else if (line.startsWith('+')) {
      return { line, type: 'added' as const }
    } else if (line.startsWith('-')) {
      return { line, type: 'removed' as const }
    } else {
      return { line, type: 'context' as const }
    }
  })
}