export interface TocHeading {
  level: number
  text: string
  slug: string
}

export function generateSlug(text: string, existingSlugs?: Set<string>): string {
  let slug = text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')

  if (slug === '') slug = 'section'

  if (!existingSlugs) return slug

  if (!existingSlugs.has(slug)) {
    existingSlugs.add(slug)
    return slug
  }

  let counter = 1
  while (existingSlugs.has(`${slug}-${counter}`)) {
    counter++
  }
  const deduped = `${slug}-${counter}`
  existingSlugs.add(deduped)
  return deduped
}

function stripInlineMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')   // bold
    .replace(/__(.+?)__/g, '$1')        // bold alt
    .replace(/\*(.+?)\*/g, '$1')        // italic
    .replace(/_(.+?)_/g, '$1')          // italic alt
    .replace(/~~(.+?)~~/g, '$1')        // strikethrough
    .replace(/`(.+?)`/g, '$1')          // inline code
    .replace(/\[(.+?)\]\(.+?\)/g, '$1') // links
}

export function extractHeadings(markdown: string): TocHeading[] {
  const headings: TocHeading[] = []
  const slugs = new Set<string>()
  const lines = markdown.split('\n')
  let inCodeFence = false

  for (const line of lines) {
    if (/^```/.test(line)) {
      inCodeFence = !inCodeFence
      continue
    }
    if (inCodeFence) continue

    const match = /^(#{1,6})\s+(.+)$/.exec(line)
    if (match) {
      const level = match[1].length
      const text = stripInlineMarkdown(match[2].trim())
      const slug = generateSlug(text, slugs)
      headings.push({ level, text, slug })
    }
  }

  return headings
}
