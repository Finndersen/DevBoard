/**
 * Format agent role string into a concise human-readable display name.
 *
 * Examples:
 * - "project" -> "Project"
 * - "task_planning" -> "Planning"
 * - "task_implementation" -> "Implementation"
 * - "task_pr_review" -> "PR Review"
 * - "investigation" -> "Investigation"
 */
export function formatAgentRoleDisplayName(agentRole: string): string {
  const role = agentRole.startsWith('task_') ? agentRole.slice('task_'.length) : agentRole

  return role
    .split('_')
    .map(word => word === 'pr' ? 'PR' : word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
