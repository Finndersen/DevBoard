// Helper functions for creating approval keys
export const createProjectApprovalKey = (projectId: string | number) => `project-${projectId}`
export const createTaskApprovalKey = (taskId: string | number) => `task-${taskId}`