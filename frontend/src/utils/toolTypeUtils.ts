/**
 * Utility functions for tool type detection and display
 */

import type { PendingApproval } from '../lib/api'

export interface DocumentEdit {
  old_string: string
  new_string: string
}

export function isSetContentTool(toolName: string): boolean {
  return toolName.startsWith('set_') && toolName.endsWith('_content')
}

export function isEditTool(toolName: string): boolean {
  return toolName.startsWith('edit_')
}

export function isDocumentTool(toolName: string): boolean {
  return isEditTool(toolName) || isSetContentTool(toolName)
}

/**
 * Extract document type from tool name (e.g., 'edit_task_specification' -> 'task_specification')
 */
export function getDocumentTypeFromToolName(toolName: string): string | null {
  if (toolName.startsWith('edit_')) {
    return toolName.replace('edit_', '')
  }
  if (toolName.startsWith('set_') && toolName.endsWith('_content')) {
    return toolName.replace('set_', '').replace('_content', '')
  }
  return null
}

/**
 * Get display-friendly document type name
 */
export function getDocumentTypeDisplay(documentType: string | null): string {
  switch (documentType) {
    case 'task_specification':
      return 'Task Specification'
    case 'task_implementation_plan':
    case 'implementation_plan':
      return 'Implementation Plan'
    case 'project_specification':
      return 'Project Specification'
    case 'initiative_context':
      return 'Initiative Context'
    default:
      return documentType || 'Document'
  }
}

/**
 * Extract edits from tool_args for edit tools
 */
export function getEditsFromToolArgs(approval: PendingApproval): DocumentEdit[] | null {
  if (!isEditTool(approval.tool_name) || !approval.tool_args) {
    return null
  }
  const edits = approval.tool_args.edits
  return (edits && Array.isArray(edits)) ? edits as DocumentEdit[] : null
}

/**
 * Extract content from tool_args for set_content tools
 */
export function getContentFromToolArgs(approval: PendingApproval): string | null {
  if (!isSetContentTool(approval.tool_name) || !approval.tool_args) {
    return null
  }
  const content = approval.tool_args.content
  return typeof content === 'string' ? content : null
}

/**
 * Extract reasoning from tool_args
 */
export function getReasoningFromToolArgs(approval: PendingApproval): string | null {
  if (!approval.tool_args) {
    return null
  }
  const reasoning = approval.tool_args.reasoning
  return typeof reasoning === 'string' ? reasoning : null
}

/**
 * Extract diff preview from tool_args (if backend provides it)
 */
export function getDiffPreviewFromToolArgs(approval: PendingApproval): string | null {
  if (!approval.tool_args) {
    return null
  }
  const diffPreview = approval.tool_args.diff_preview
  return typeof diffPreview === 'string' ? diffPreview : null
}
