// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { generateSlug, extractHeadings } from '../markdown'

describe('generateSlug', () => {
  it('converts basic text to a slug', () => {
    expect(generateSlug('Hello World')).toBe('hello-world')
  })

  it('strips special characters', () => {
    expect(generateSlug('Hello, World! (2024)')).toBe('hello-world-2024')
  })

  it('converts spaces to hyphens', () => {
    expect(generateSlug('multiple   spaced   words')).toBe('multiple-spaced-words')
  })

  it('collapses consecutive hyphens', () => {
    expect(generateSlug('hello---world')).toBe('hello-world')
  })

  it('strips leading and trailing hyphens', () => {
    expect(generateSlug('--hello--')).toBe('hello')
  })

  it('returns deduplicated slug with numeric suffix when existingSlugs has collision', () => {
    const slugs = new Set<string>(['hello-world'])
    expect(generateSlug('Hello World', slugs)).toBe('hello-world-1')
  })

  it('increments suffix for multiple collisions', () => {
    const slugs = new Set<string>(['intro', 'intro-1', 'intro-2'])
    expect(generateSlug('Intro', slugs)).toBe('intro-3')
  })

  it('adds first occurrence to the set when no collision', () => {
    const slugs = new Set<string>()
    generateSlug('New Heading', slugs)
    expect(slugs.has('new-heading')).toBe(true)
  })

  it('adds deduplicated slug to the set on collision', () => {
    const slugs = new Set<string>(['setup'])
    generateSlug('Setup', slugs)
    expect(slugs.has('setup-1')).toBe(true)
  })

  it('does not track slugs when existingSlugs is not provided', () => {
    const first = generateSlug('Same Title')
    const second = generateSlug('Same Title')
    expect(first).toBe(second)
  })
})

describe('extractHeadings', () => {
  it('extracts headings at multiple levels', () => {
    const md = '# Title\n## Subtitle\n### Section\n#### Subsection'
    expect(extractHeadings(md)).toEqual([
      { level: 1, text: 'Title', slug: 'title' },
      { level: 2, text: 'Subtitle', slug: 'subtitle' },
      { level: 3, text: 'Section', slug: 'section' },
      { level: 4, text: 'Subsection', slug: 'subsection' },
    ])
  })

  it('returns correct level numbers up to h6', () => {
    const md = '##### Level 5\n###### Level 6'
    expect(extractHeadings(md)).toEqual([
      { level: 5, text: 'Level 5', slug: 'level-5' },
      { level: 6, text: 'Level 6', slug: 'level-6' },
    ])
  })

  it('strips bold formatting', () => {
    const md = '## **Bold** heading'
    expect(extractHeadings(md)).toEqual([
      { level: 2, text: 'Bold heading', slug: 'bold-heading' },
    ])
  })

  it('strips italic formatting', () => {
    const md = '## *Italic* heading'
    expect(extractHeadings(md)).toEqual([
      { level: 2, text: 'Italic heading', slug: 'italic-heading' },
    ])
  })

  it('strips inline code formatting', () => {
    const md = '## The `config` file'
    expect(extractHeadings(md)).toEqual([
      { level: 2, text: 'The config file', slug: 'the-config-file' },
    ])
  })

  it('strips strikethrough formatting', () => {
    const md = '## ~~Old~~ New'
    expect(extractHeadings(md)).toEqual([
      { level: 2, text: 'Old New', slug: 'old-new' },
    ])
  })

  it('strips link formatting keeping link text', () => {
    const md = '## See [the docs](https://example.com) for details'
    expect(extractHeadings(md)).toEqual([
      { level: 2, text: 'See the docs for details', slug: 'see-the-docs-for-details' },
    ])
  })

  it('ignores headings inside code fences', () => {
    const md = [
      '# Real Heading',
      '```',
      '# Not a heading',
      '## Also not a heading',
      '```',
      '## Another Real Heading',
    ].join('\n')
    expect(extractHeadings(md)).toEqual([
      { level: 1, text: 'Real Heading', slug: 'real-heading' },
      { level: 2, text: 'Another Real Heading', slug: 'another-real-heading' },
    ])
  })

  it('ignores headings inside code fences with language specifier', () => {
    const md = [
      '# Before',
      '```python',
      '# comment in code',
      '```',
      '# After',
    ].join('\n')
    expect(extractHeadings(md)).toEqual([
      { level: 1, text: 'Before', slug: 'before' },
      { level: 1, text: 'After', slug: 'after' },
    ])
  })

  it('handles duplicate heading text with slug suffixes', () => {
    const md = '## Setup\n## Setup\n## Setup'
    expect(extractHeadings(md)).toEqual([
      { level: 2, text: 'Setup', slug: 'setup' },
      { level: 2, text: 'Setup', slug: 'setup-1' },
      { level: 2, text: 'Setup', slug: 'setup-2' },
    ])
  })

  it('returns empty array for content with no headings', () => {
    const md = 'Just some regular text.\n\nAnother paragraph.'
    expect(extractHeadings(md)).toEqual([])
  })

  it('returns empty array for empty string', () => {
    expect(extractHeadings('')).toEqual([])
  })

  it('ignores lines that look like headings but lack a space after hashes', () => {
    const md = '##NoSpace\n## With Space'
    expect(extractHeadings(md)).toEqual([
      { level: 2, text: 'With Space', slug: 'with-space' },
    ])
  })
})
