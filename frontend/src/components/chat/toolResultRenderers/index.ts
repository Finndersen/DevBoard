/**
 * Tool Result Renderer Registry
 *
 * Maps tool names to custom React components that render tool calls or results
 * in interactive, user-friendly formats instead of the standard collapsible display.
 */

import type { ComponentType, JSX } from 'react'

import type { ToolCall, ToolResult } from '../../../lib/api'

import CreateTaskResultRenderer from './CreateTaskResultRenderer'
import EditTaskResultRenderer from './EditTaskResultRenderer'
import SubAgentResultRenderer from './SubAgentResultRenderer'

/**
 * Props passed to all rich result renderer components.
 */
export interface RichResultRendererProps {
  /** Parsed JSON data from the tool result */
  data: unknown
  /** The original tool call for additional context */
  toolCall: ToolCall
}

/**
 * A React component that renders a rich tool result.
 */
export type RichResultRenderer = ComponentType<RichResultRendererProps>

/**
 * Registry mapping tool names to their rich renderer components.
 * Tools not in this registry will fall back to plain text display.
 */
const richResultRenderers: Record<string, RichResultRenderer> = {
  create_task: CreateTaskResultRenderer,
  edit_task: EditTaskResultRenderer,
  investigate_codebase: SubAgentResultRenderer,
  execute_implementation_step: SubAgentResultRenderer,
  review_code_changes: SubAgentResultRenderer,
}

/**
 * Look up a rich renderer for a tool by name.
 *
 * @param toolName - The name of the tool
 * @returns The renderer component if one exists, or null for plain text fallback
 */
export function getRichResultRenderer(toolName: string): RichResultRenderer | null {
  return richResultRenderers[toolName] ?? null
}

/**
 * Attempt to parse a tool result as JSON.
 *
 * @param resultContent - The raw result content string
 * @returns Parsed JSON data if successful, or null if parsing fails
 */
export function tryParseToolResult(resultContent: string): unknown | null {
  try {
    return JSON.parse(resultContent)
  } catch {
    return null
  }
}

/**
 * Props passed to custom tool display components.
 * These completely replace the standard ToolCallDisplay for specific tools.
 */
export interface CustomToolDisplayProps {
  toolCall: ToolCall
  toolResult?: ToolResult
}

/**
 * A React component that fully replaces the standard ToolCallDisplay for a tool.
 */
export type CustomToolDisplay = (props: CustomToolDisplayProps) => JSX.Element

/**
 * Registry mapping tool names to custom display components that replace
 * the standard collapsible ToolCallDisplay entirely.
 */
const customToolDisplays: Record<string, CustomToolDisplay> = {
}

/**
 * Look up a custom display component for a tool by name.
 *
 * @param toolName - The name of the tool
 * @returns The custom display component if one exists, or null to use standard display
 */
export function getCustomToolDisplay(toolName: string): CustomToolDisplay | null {
  return customToolDisplays[toolName] ?? null
}
