// Helper functions for creating approval keys
export const createConversationApprovalKey = (conversationId: string | number) => `conversation-${conversationId}`
export const createProjectApprovalKey = (projectId: string | number) => `project-${projectId}`
export const createTaskApprovalKey = (taskId: string | number) => `task-${taskId}`

// Helper functions for creating pending message keys
export const createConversationPendingKey = (conversationId: string | number) => `conversation-${conversationId}`