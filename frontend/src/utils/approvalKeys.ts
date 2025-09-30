// Helper functions for creating approval keys
export const createConversationApprovalKey = (conversationId: string | number) => `conversation-${conversationId}`
export const createProjectApprovalKey = (projectId: string | number) => `project-${projectId}`
export const createTaskApprovalKey = (taskId: string | number) => `task-${taskId}`

// Helper functions for creating pending message keys
export const createConversationPendingKey = (conversationId: string | number) => `conversation-${conversationId}`

// Helper functions for extracting IDs from approval keys
export const extractConversationIdFromKey = (key: string): number | null => {
  if (key.startsWith('conversation-')) {
    const idStr = key.replace('conversation-', '')
    const id = parseInt(idStr, 10)
    return isNaN(id) ? null : id
  }
  return null
}

export const extractProjectIdFromKey = (key: string): number | null => {
  if (key.startsWith('project-')) {
    const idStr = key.replace('project-', '')
    const id = parseInt(idStr, 10)
    return isNaN(id) ? null : id
  }
  return null
}

export const extractTaskIdFromKey = (key: string): number | null => {
  if (key.startsWith('task-')) {
    const idStr = key.replace('task-', '')
    const id = parseInt(idStr, 10)
    return isNaN(id) ? null : id
  }
  return null
}

// Helper function to determine the type of approval key
export type ApprovalKeyType = 'conversation' | 'project' | 'task' | 'unknown'

export const getApprovalKeyType = (key: string): ApprovalKeyType => {
  if (key.startsWith('conversation-')) return 'conversation'
  if (key.startsWith('project-')) return 'project'
  if (key.startsWith('task-')) return 'task'
  return 'unknown'
}