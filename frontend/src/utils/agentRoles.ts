/**
 * Format agent role string into a human-readable display name.
 *
 * Examples:
 * - "project" -> "Project Agent"
 * - "task_planning" -> "Task Planning Agent"
 * - "task_implementation" -> "Task Implementation Agent"
 * - "task_pr_review" -> "Task Pr Review Agent"
 * - "investigation" -> "Investigation Agent"
 */
export function formatAgentRoleDisplayName(agentRole: string): string {
  const words = agentRole
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

  return `${words} Agent`
}
