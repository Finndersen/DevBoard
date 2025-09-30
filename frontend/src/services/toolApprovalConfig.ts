/**
 * Tool Approval Configuration Service
 * 
 * Provides explicit mapping between tool names and their refresh requirements.
 * No pattern matching - all tool mappings are explicitly configured.
 */

export interface ToolApprovalConfig {
  toolName: string
  documentType: 'project_specification' | 'task_specification' | 'task_implementation_plan'
  refreshAction: 'refresh_project' | 'refresh_task'
}

export interface RefreshHandler {
  conversationId: number
  refreshAction: string
  callback: () => Promise<void>
}

/**
 * Static configuration mapping tool names to refresh requirements
 */
export const TOOL_APPROVAL_CONFIGS: ToolApprovalConfig[] = [
  {
    toolName: 'edit_project_specification',
    documentType: 'project_specification',
    refreshAction: 'refresh_project'
  },
  {
    toolName: 'edit_task_specification',
    documentType: 'task_specification',
    refreshAction: 'refresh_task'
  },
  {
    toolName: 'edit_task_implementation_plan',
    documentType: 'task_implementation_plan',
    refreshAction: 'refresh_task'
  }
]

/**
 * Service class for managing tool approval configurations
 */
export class ToolApprovalConfigService {
  private static instance: ToolApprovalConfigService
  private configMap: Map<string, ToolApprovalConfig>

  private constructor() {
    // Build lookup map for O(1) access
    this.configMap = new Map()
    for (const config of TOOL_APPROVAL_CONFIGS) {
      this.configMap.set(config.toolName, config)
    }
  }

  static getInstance(): ToolApprovalConfigService {
    if (!ToolApprovalConfigService.instance) {
      ToolApprovalConfigService.instance = new ToolApprovalConfigService()
    }
    return ToolApprovalConfigService.instance
  }

  /**
   * Get the configuration for a specific tool name
   */
  getToolConfig(toolName: string): ToolApprovalConfig | undefined {
    return this.configMap.get(toolName)
  }

  /**
   * Get the refresh action required for a tool
   */
  getRefreshAction(toolName: string): string | undefined {
    const config = this.getToolConfig(toolName)
    return config?.refreshAction
  }

  /**
   * Check if a tool requires refresh after approval
   */
  requiresRefresh(toolName: string): boolean {
    return this.configMap.has(toolName)
  }

  /**
   * Get all refresh actions required for a list of tool names
   */
  getRequiredRefreshActions(toolNames: string[]): string[] {
    const refreshActions = new Set<string>()
    
    for (const toolName of toolNames) {
      const refreshAction = this.getRefreshAction(toolName)
      if (refreshAction) {
        refreshActions.add(refreshAction)
      }
    }
    
    return Array.from(refreshActions)
  }

  /**
   * Get all configured tool names (for debugging/testing)
   */
  getAllToolNames(): string[] {
    return Array.from(this.configMap.keys())
  }
}

// Export singleton instance
export const toolApprovalConfig = ToolApprovalConfigService.getInstance()