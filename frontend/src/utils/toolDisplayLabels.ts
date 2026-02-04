/**
 * Utility functions for generating display labels for tool calls.
 * These labels provide more informative context in the UI by including
 * relevant arguments like file paths, search patterns, and descriptions.
 */

export interface ToolDisplayLabel {
  toolName: string
  details?: string
}

/**
 * Strip MCP prefixes from tool names for cleaner display.
 * - Removes `mcp__builtin_tools__` prefix completely
 * - Removes only `mcp__` prefix for other MCP servers (keeps server name for context)
 */
export function cleanToolName(toolName: string): string {
  // Remove mcp__builtin_tools__ prefix completely (these are standard tools)
  if (toolName.startsWith('mcp__builtin_tools__')) {
    return toolName.replace('mcp__builtin_tools__', '')
  }

  // For other MCP servers, only remove the `mcp__` prefix but keep the server name
  // e.g., mcp__github__get_repo -> github__get_repo
  if (toolName.startsWith('mcp__')) {
    return toolName.replace('mcp__', '')
  }

  return toolName
}

/**
 * Convert absolute paths to relative paths based on codebase local path.
 * Handles both main repo paths and worktree variant paths.
 *
 * @param absolutePath - The absolute file path
 * @param codebaseLocalPath - The codebase's local_path (e.g., /Users/dev/projects/myrepo)
 * @returns Relative path or original path if no match
 */
export function relativizePath(absolutePath: string, codebaseLocalPath?: string): string {
  if (!codebaseLocalPath || !absolutePath) {
    return absolutePath
  }

  // Try main repo path first: <local_path>/
  const mainRepoPrefix = codebaseLocalPath + '/'
  if (absolutePath.startsWith(mainRepoPrefix)) {
    return absolutePath.slice(mainRepoPrefix.length)
  }

  // Try worktree variant: <local_path>.worktree-\d+/
  // e.g., /Users/dev/projects/myrepo.worktree-2/src/file.ts
  const worktreePattern = new RegExp(`^${escapeRegExp(codebaseLocalPath)}\\.worktree-\\d+/`)
  const worktreeMatch = absolutePath.match(worktreePattern)
  if (worktreeMatch) {
    return absolutePath.slice(worktreeMatch[0].length)
  }

  return absolutePath
}

/**
 * Escape special regex characters in a string.
 */
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Generate a display label for a tool call based on tool name and arguments.
 *
 * @param toolName - The raw tool name (may include MCP prefixes)
 * @param toolArgs - The tool arguments object (or null)
 * @param codebaseLocalPath - Optional codebase path for relativizing file paths
 * @returns An object with toolName and optional details for separate styling
 */
export function getToolDisplayLabel(
  toolName: string,
  toolArgs: Record<string, unknown> | null,
  codebaseLocalPath?: string
): ToolDisplayLabel {
  const cleanedName = cleanToolName(toolName)
  const args = toolArgs || {}

  switch (cleanedName) {
    case 'Read': {
      const filePath = args.file_path as string | undefined
      if (filePath) {
        return { toolName: 'Read', details: relativizePath(filePath, codebaseLocalPath) }
      }
      return { toolName: cleanedName }
    }

    case 'Edit': {
      const filePath = args.file_path as string | undefined
      if (filePath) {
        return { toolName: 'Edit', details: relativizePath(filePath, codebaseLocalPath) }
      }
      return { toolName: cleanedName }
    }

    case 'Write': {
      const filePath = args.file_path as string | undefined
      if (filePath) {
        return { toolName: 'Write', details: relativizePath(filePath, codebaseLocalPath) }
      }
      return { toolName: cleanedName }
    }

    case 'Bash': {
      const description = args.description as string | undefined
      if (description) {
        return { toolName: 'Bash', details: description }
      }
      const command = args.command as string | undefined
      if (command) {
        return { toolName: 'Bash', details: command }
      }
      return { toolName: cleanedName }
    }

    case 'Grep': {
      const pattern = args.pattern as string | undefined
      const path = args.path as string | undefined
      if (pattern && path) {
        return { toolName: 'Grep', details: `"${pattern}" in ${relativizePath(path, codebaseLocalPath)}` }
      }
      if (pattern) {
        return { toolName: 'Grep', details: `"${pattern}"` }
      }
      return { toolName: cleanedName }
    }

    case 'Glob': {
      const pattern = args.pattern as string | undefined
      if (pattern) {
        return { toolName: 'Glob', details: pattern }
      }
      return { toolName: cleanedName }
    }

    case 'WebFetch': {
      const url = args.url as string | undefined
      if (url) {
        return { toolName: 'WebFetch', details: url }
      }
      return { toolName: cleanedName }
    }

    case 'WebSearch': {
      const query = args.query as string | undefined
      if (query) {
        return { toolName: 'WebSearch', details: query }
      }
      return { toolName: cleanedName }
    }

    case 'Task': {
      const description = args.description as string | undefined
      if (description) {
        return { toolName: 'Task', details: description }
      }
      return { toolName: cleanedName }
    }

    case 'investigate_codebase': {
      const query = args.query as string | undefined
      if (query) {
        return { toolName: 'investigate_codebase', details: query }
      }
      return { toolName: cleanedName }
    }

    default:
      return { toolName: cleanedName }
  }
}

/**
 * Format a ToolDisplayLabel as a single string (for tooltips, etc.)
 */
export function formatToolDisplayLabel(label: ToolDisplayLabel): string {
  return label.details ? `${label.toolName}: ${label.details}` : label.toolName
}
