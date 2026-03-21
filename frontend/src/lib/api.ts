import { createWebSocketEventStream } from './websocketStream'

export enum TaskStatus {
  PLANNING = 'planning',
  IMPLEMENTING = 'implementing',
  PR_OPEN = 'pr_open',
  COMPLETE = 'complete',
}

export interface Project {
  id: number
  name: string
  specification_document_id: number
  description: string
  default_conversation_id: number | null
  created_at: string
  custom_fields: Record<string, unknown> | null
}

export interface WorkflowActionInfo {
  key: string
}

export interface Task {
  id: number
  title: string
  status: TaskStatus
  project_id: number
  codebase_id: number
  conversation_id: number
  created_at: string
  specification_document_id: number
  implementation_plan_document_id: number | null
  implementation_plan_id: number | null
  change_summary_document_id: number | null
  custom_fields: Record<string, unknown> | null
  github_pr_number: number | null
  available_workflow_actions: WorkflowActionInfo[]
}

export type ImplementationStepType = 'code_change' | 'documentation' | 'validation' | 'code_review'
export type ImplementationStepStatus = 'pending' | 'running' | 'complete' | 'failed' | 'skipped'
export interface ImplementationStepResponse {
  id: number
  step_number: number
  title: string
  type: ImplementationStepType
  dependencies: number[]
  status: ImplementationStepStatus
  details: string
  outcome: string | null
  started_at: string | null
  completed_at: string | null
}

export interface ImplementationPlanResponse {
  id: number
  task_id: number
  overview: string | null
  status: string
  steps: ImplementationStepResponse[]
}

export interface ImplementationStepUpdate {
  title?: string
  type?: ImplementationStepType
  dependencies?: number[]
  details?: string
}

export interface TaskListItem {
  id: number
  title: string
  project_id: number
  project_name: string
  codebase_id: number
  status: TaskStatus
  created_at: string
}

export interface GitHubPRStatusResponse {
  pr_number: number
  pr_url: string
  state: string
  merged: boolean
  mergeable_state: string | null
  review_decision: string | null
  ci_status: string | null
  comment_count: number
}

export interface PRFeedbackComment {
  id: number
  author: string
  body: string
  path: string
  line: number | null
  diff_hunk: string | null
  created_at: string | null
  in_reply_to_id: number | null
}

export interface PRFeedbackCommentThread {
  original: PRFeedbackComment
  replies: PRFeedbackComment[]
}

export interface PRFeedbackReview {
  id: number
  author: string
  state: string
  body: string
  submitted_at: string | null
  comment_threads: PRFeedbackCommentThread[]
}

export interface PRFeedbackResponse {
  reviews: PRFeedbackReview[]
  standalone_threads: PRFeedbackCommentThread[]
}

export interface TaskCreate {
  title: string
  codebase_id: number
  specification_content: string | null
  branch_name?: string  // Optional - auto-generated if not provided
  base_branch?: string  // Optional - defaults to "main"
  custom_fields?: Record<string, unknown> | null
}

// Custom Field Definition types
export type CustomFieldType = 'text' | 'boolean' | 'enum'
export type CustomFieldEntityType = 'task' | 'project' | 'codebase'

export interface CustomFieldDefinition {
  id: number
  name: string
  entity_type: CustomFieldEntityType
  description: string | null
  type: CustomFieldType
  options: string[] | null
  mandatory: boolean
  created_at: string
}

export interface CustomFieldCreate {
  name: string
  entity_type?: CustomFieldEntityType
  description?: string | null
  type: CustomFieldType
  options?: string[] | null
  mandatory?: boolean
}

export interface CustomFieldUpdate {
  name?: string | null
  description?: string | null
  type?: CustomFieldType | null
  options?: string[] | null
  mandatory?: boolean | null
}

export interface DocumentResponse {
  id: number
  document_type: string
  content: string
  content_hash: string
  created_at: string
  updated_at: string
}

// New agent conversation interfaces matching backend schemas
export type MessageRole = 'user' | 'agent'

export type ConversationEventType = 'message' | 'tool_call' | 'tool_result' | 'tool_call_request' | 'system' | 'meta_message' | 'local_command' | 'thinking'

export type MetaMessageType = 'compact_summary' | 'skill_content'

export interface MetaMessage {
  event_type: 'meta_message'
  meta_type: MetaMessageType
  text_content: string
  timestamp: string
  uuid?: string
}

export type LocalCommandType = 'shell' | 'slash_command'

export interface LocalCommand {
  event_type: 'local_command'
  command_type: LocalCommandType
  command: string
  output: string
  is_error: boolean
  timestamp: string
  uuid?: string
}

export type SystemEventType = 'task_updated' | 'conversation_updated' | 'workspace_allocate' | 'workspace_branch_checkout' | 'workspace_create' | 'workspace_setup' | 'stream_error' | 'stream_interrupted' | 'branch_rebased' | 'stash_apply_conflict' | 'session_expired' | 'compacting_conversation' | 'rate_limit'

export interface ConversationMessage {
  event_type: 'message'
  role: MessageRole
  text_content: string
  timestamp: string
  uuid?: string
}

export interface ToolCall {
  event_type: 'tool_call'
  tool_call_id: string
  tool_name: string
  tool_args: Record<string, unknown> | null
  timestamp: string
  uuid?: string
}

export interface ToolResult {
  event_type: 'tool_result'
  tool_call_id: string
  result_content: string
  is_error: boolean
  timestamp: string
  uuid?: string
}

export interface ToolCallRequest {
  event_type: 'tool_call_request'
  tool_call_id: string
  tool_name: string
  tool_args: string | Record<string, unknown> | null
  timestamp: string
}

export interface SystemEvent {
  event_type: 'system'
  type: SystemEventType
  data: Record<string, unknown> | null
  timestamp: string
}

export interface ThinkingEvent {
  event_type: 'thinking'
  duration_seconds: number | null
  timestamp: string
  uuid?: string
}

// Union type for all conversation events
export type ConversationEvent = ConversationMessage | ToolCall | ToolResult | ToolCallRequest | SystemEvent | MetaMessage | LocalCommand | ThinkingEvent

export interface UserPrompt {
  message: string
}

export interface ToolApprovalDecision {
  approved: boolean
  feedback?: string
}

export interface ToolApprovalRequest {
  approvals: Record<string, ToolApprovalDecision>
}

// Main PendingApproval interface - generic structure to support any tool type
export interface PendingApproval {
  tool_call_id: string
  tool_name: string
  tool_args: Record<string, unknown> | null  // Generic tool arguments, structure depends on tool type
}

export interface CommitMetadata {
  commit_hash: string
  author: string
  date: string
  message: string
}

export interface TaskBranchInfo {
  commits: CommitMetadata[]
  has_uncommitted_changes: boolean
}

export interface FileDiff {
  file_path: string
  diff_content: string
  additions: number
  deletions: number
  is_new_file?: boolean
  is_deleted?: boolean
}

export interface TaskDiffResponse {
  files: FileDiff[]
  additions: number
  deletions: number
  generated_at: string
}

export interface StateTransitionRequest {
  new_state: string
}

export interface PromptActionRequest {
  action_key: string
}

export interface Integration {
  id: string
  name: string
  type: string
  status: 'connected' | 'disconnected'
  config: Record<string, unknown>
}

export interface LLMProvider {
  id: string
  name: string
  type: string
  enabled: boolean
  config: Record<string, unknown>
}

export type MergeMethod = 'squash' | 'rebase' | 'merge_commit'
export type BranchHandling = 'local_merge' | 'github_pr' | 'manual'

export interface Codebase {
  id: number
  name: string
  description: string
  repository_url: string | null
  local_path: string
  default_branch: string
  merge_method: MergeMethod
  branch_handling: BranchHandling
  max_worktrees: number | null
  setup_command: string | null
  developer_context: string | null
}

export interface CodebaseCreate {
  name: string
  description: string
  local_path: string
  default_branch?: string | null
  merge_method?: MergeMethod | null
  branch_handling?: BranchHandling | null
  max_worktrees?: number | null
  setup_command?: string | null
  developer_context?: string | null
}

// Git and Worktree Management
export interface TaskGitStatus {
  branch_name: string
  branch_exists: boolean
  base_branch: string
  commits_ahead: number
  commits_behind: number
  can_merge: boolean
  has_conflicts: boolean
  worktree_slot: WorktreeSlotInfo | null
  // New fields for branch status modal
  worktree_slot_path: string | null
  main_repo_is_clean: boolean
  main_repo_current_branch: string | null
  // Rebase state
  rebase_in_progress: boolean
  has_uncommitted_base_overlap: boolean
  remote_fetch_failed: boolean
}

export interface WorktreeSlotInfo {
  id: number
  path: string
  locked: boolean
  locked_since: string | null
}

export interface TaskInfoSimple {
  id: number
  title: string
}

export interface WorktreeSlot {
  id: number
  path: string
  is_main_repo: boolean
  status: 'locked' | 'available' | 'missing'
  current_branch: string | null
  last_used_at: string | null
  locked_by_task: TaskInfoSimple | null
  last_used_by_task: TaskInfoSimple | null
  has_uncommitted_changes: boolean
  uncommitted_change_count: number
}

export interface TaskInfo {
  id: number
  title: string
  branch: string
}

export interface WorktreePoolStatus {
  codebase_id: number
  codebase_path: string
  slots: WorktreeSlot[]
  stats: {
    total_slots: number
    available: number
    locked: number
  }
}

export interface MergeBranchRequest {
  target_branch?: string
  delete_branch?: boolean
}

export interface MergeBranchResponse {
  success: boolean
  merge_commit: string
}

export interface CheckoutToMainResponse {
  success: boolean
  message: string
}

export interface WorkspaceAllocationResponse {
  slot: WorktreeSlotInfo
  branch_checked_out: boolean
  ready: boolean
}

export interface AllSlotsLockedResponse {
  error: 'ALL_SLOTS_LOCKED'
  locked_by: Array<{
    task_id: number
    title: string
    slot: string
  }>
  can_create_new: boolean
}

export interface ArchitectureDocument {
  exists: boolean
  content: string | null
  content_hash: string | null
  file_path: string | null
  size_bytes: number | null
}

export interface ArchitectureUpdateRequest {
  content: string
  original_hash: string | null
}

export interface ArchitectureUpdateResponse {
  success: boolean
  content_hash: string | null
  message: string | null
  error_type?: string
  current_hash?: string
}

export interface ArchitectureGenerationRequest {
  preserve_user_sections?: boolean
}

export interface ArchitectureGenerationResponse {
  success: boolean
  file_path: string | null
  content: string | null
  error_message: string | null
  error_type: string | null
}

export interface ConfigurationFieldInfo {
  name: string
  type: 'string' | 'boolean' | 'integer' | 'number' | 'enum'
  required: boolean
  description?: string
  env_value?: unknown
  db_value?: unknown
  default_value?: unknown
  is_secret: boolean
  env_var_name?: string
  is_overridden: boolean
  effective_value: unknown
  enum_values?: string[]
}

export interface ConfigurationDetailResponse {
  key: string
  fields: ConfigurationFieldInfo[]
  is_valid: boolean
  validation_errors?: string[]
}

export interface IntegrationTestResponse {
  success: boolean
  error_type?: string
  error_message?: string
  details?: Record<string, unknown>
}

export interface ModelInfo {
  id: string
  provider: string
  name: string
  model_type: 'fast' | 'standard' | 'advanced'
}

export interface AgentEngineInfo {
  engine: string
  display_name: string
  description: string
  requires_model_selection: boolean
  is_available: boolean
  unavailable_reason: string | null
}

export interface AgentEngineModelConfig {
  engine: string
  model_id: string | null
}

export interface AgentConfigurationResponse {
  agent_role: string
  config: AgentEngineModelConfig
  custom_instructions: string | null
  available_engines: AgentEngineInfo[]
  enabled_mcp_tools: MCPToolSummary[]
}

export interface UpdateAgentConfigurationRequest {
  engine: string
  model_id: string | null
  custom_instructions?: string | null
}

export interface MCPToolSummary {
  tool_id: number
  tool_name: string
  server_name: string
  description: string | null
}

export interface AgentRoleToolsResponse {
  role: string
  tools: MCPToolSummary[]
}

export interface AvailableModelsByEngineResponse {
  models_by_engine: Record<string, ModelInfo[]>
}

export interface UpdateConversationModelRequest {
  model_id: string | null
}

// MCP Server Configuration types
export type MCPServerType = 'stdio' | 'http'

export interface StdioMCPConfig {
  command: string
  args?: string[]
  env?: Record<string, string> | null
}

export type HttpAuthType = 'none' | 'bearer' | 'oauth'

export interface HttpMCPConfig {
  url: string
  auth_type?: HttpAuthType
  bearer_token?: string | null
  client_id?: string | null
  client_secret?: string | null
  scopes?: string | null
}

export type MCPConfigJson = StdioMCPConfig | HttpMCPConfig

export interface MCPServerConfig {
  id: number
  name: string
  server_type: MCPServerType
  config_json: MCPConfigJson
  last_verified_at: string | null
  last_verified_success: boolean | null
  last_verified_error: string | null
}

export interface MCPServerConfigCreate {
  name: string
  server_type: MCPServerType
  config_json: MCPConfigJson
}

export interface MCPServerConfigUpdate {
  name?: string | null
  server_type?: MCPServerType | null
  config_json?: MCPConfigJson | null
}

export interface MCPToolInfo {
  name: string
  description: string | null
  input_schema: Record<string, unknown> | null
}

export interface MCPTool {
  id: number
  name: string
  description: string | null
  input_schema: Record<string, unknown> | null
  parameter_count: number
}

export interface MCPToolUpdate {
  description: string | null
}

export interface OAuthStatus {
  has_tokens: boolean
  token_expired: boolean
  has_client_info: boolean
}

export interface MCPServerDetail {
  id: number
  name: string
  server_type: MCPServerType
  config_json: MCPConfigJson
  last_verified_at: string | null
  last_verified_success: boolean | null
  last_verified_error: string | null
  tools: MCPTool[]
  oauth_status?: OAuthStatus | null
}

export interface VerifyResult {
  success: boolean
  tools: MCPToolInfo[] | null
  error: string | null
}

export interface MCPToolRunRequest {
  arguments?: Record<string, unknown>
}

export interface MCPToolRunResponse {
  success: boolean
  result?: string
  error?: string
}

export interface ConversationResponse {
  id: number
  parent_entity_type: string
  parent_entity_id: number
  agent_role: string
  engine: string
  model_id: string | null
  is_active: boolean
  external_session_id: string | null
  title: string | null
  last_activity_at: string | null
  created_at: string
  parent_entity_name: string | null
  project_name: string | null
}

export interface CreateConversationResponse extends ConversationResponse {
  at_cap: boolean
}

export interface ToolInfo {
  name: string
  description: string | null
  input_schema: Record<string, unknown> | null
  source: 'role' | 'mcp' | 'builtin'
  server_name: string | null
}

export interface AgentConfigResponse {
  agent_role: string
  behaviour_guidelines: string
  context_content: string
  custom_instructions: string | null
  role_tools: ToolInfo[]
  mcp_tools: ToolInfo[]
  builtin_tools: ToolInfo[]
}

// Todo list types for Claude Code conversations
export type TodoStatus = 'pending' | 'in_progress' | 'completed'

export interface TodoItem {
  content: string
  status: TodoStatus
  active_form: string | null
  priority: string | null
  id: string | null
}

// Claude Code Session Viewer types
export interface ClaudeCodeProject {
  path: string
  encoded_path: string
  last_activity: string | null
  session_count: number
}

export interface SessionTaskInfo {
  task_id: number
  task_title: string
  agent_role: string
}

export interface SubAgentInfo {
  agent_role: string
  parent_task_id: number | null
  parent_task_title: string | null
}

export interface ClaudeCodeSession {
  session_id: string
  label: string
  last_activity: string
  start_time: string
  file_size: number
  is_empty: boolean
  linked_session_id: string | null
  session_role: 'plan' | 'implementation' | null
  task_info: SessionTaskInfo | null
  sub_agent_info: SubAgentInfo | null
}

export interface SessionSearchResult {
  session_id: string
  project_encoded_path: string
  line_number: number
  line_content: string
  message_uuid: string | null
  text_snippet: string | null
}

// GitHub PR Status types
export interface OpenPRItem {
  pr_number: number
  title: string
  repo_full_name: string
  codebase_id: number | null
  pr_url: string
  mergeable_state: string | null
  task_id: number | null
  task_title: string | null
  updated_at: string
  review_decision: string | null
  ci_status: string | null
  comment_count: number
}

export interface OpenPRsResponse {
  prs: OpenPRItem[]
  errors: string[]
}

// Active Executions
export interface ActiveExecutionItem {
  conversation_id: number
  status: 'running'
  started_at: string
  parent_entity_type: string
  agent_role: string
  task_id: number | null
  task_title: string | null
}

export interface ActiveExecutionsResponse {
  executions: ActiveExecutionItem[]
}

export interface PRCheckItem {
  name: string
  state: string
  description: string | null
}

export interface PRReviewItem {
  author: string
  state: string
  body: string
}

export interface PRDetailResponse {
  ci_status: string | null
  checks: PRCheckItem[]
  reviews: PRReviewItem[]
  review_comment_count: number
}

export class ApiClient {
  private readonly baseURL = import.meta.env.VITE_API_BASE_URL || ''

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseURL}${endpoint}`
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    })

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`)
    }

    if (response.status === 204 || response.headers.get('content-length') === '0') {
      return undefined as T
    }

    return response.json()
  }

  // Projects
  async getProjects(): Promise<Project[]> {
    return this.request<Project[]>('/api/projects')
  }

  async createProject(project: Omit<Project, 'id' | 'created_at'>): Promise<Project> {
    return this.request<Project>('/api/projects', {
      method: 'POST',
      body: JSON.stringify(project),
    })
  }

  async getProject(id: number | string): Promise<Project> {
    return this.request<Project>(`/api/projects/${id}`)
  }

  async updateProject(id: number | string, project: Partial<Project>): Promise<Project> {
    return this.request<Project>(`/api/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(project),
    })
  }

  async deleteProject(id: number | string): Promise<void> {
    return this.request<void>(`/api/projects/${id}`, { method: 'DELETE' })
  }

  // Project Codebases
  async getProjectCodebases(projectId: number | string): Promise<Codebase[]> {
    return this.request<Codebase[]>(`/api/projects/${projectId}/codebases`)
  }

  async linkCodebaseToProject(projectId: number | string, codebaseId: number | string): Promise<Codebase> {
    return this.request<Codebase>(`/api/projects/${projectId}/codebases/${codebaseId}`, {
      method: 'POST',
    })
  }

  async unlinkCodebaseFromProject(projectId: number | string, codebaseId: number | string): Promise<{ message: string; success: boolean }> {
    return this.request<{ message: string; success: boolean }>(`/api/projects/${projectId}/codebases/${codebaseId}`, {
      method: 'DELETE',
    })
  }

  // Tasks
  async getAllTasks(projectId?: number): Promise<TaskListItem[]> {
    const params = projectId ? `?project_id=${projectId}` : ''
    return this.request<TaskListItem[]>(`/api/tasks${params}`)
  }

  async getProjectTasks(projectId: number | string): Promise<Task[]> {
    return this.request<Task[]>(`/api/projects/${projectId}/tasks`)
  }

  async createTask(projectId: number | string, task: TaskCreate): Promise<Task> {
    return this.request<Task>(`/api/projects/${projectId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(task),
    })
  }

  async getTask(id: number | string): Promise<Task> {
    return this.request<Task>(`/api/tasks/${id}`)
  }

  async updateTask(id: number | string, task: Partial<Task>): Promise<Task> {
    return this.request<Task>(`/api/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(task),
    })
  }

  async deleteTask(id: number | string, deleteBranch?: boolean): Promise<void> {
    const queryParams = deleteBranch ? '?delete_branch=true' : ''
    return this.request<void>(`/api/tasks/${id}${queryParams}`, { method: 'DELETE' })
  }

  // Documents
  async getDocument(id: number | string): Promise<DocumentResponse> {
    return this.request<DocumentResponse>(`/api/documents/${id}`)
  }

  async updateDocument(id: number | string, content: string): Promise<DocumentResponse> {
    return this.request<DocumentResponse>(`/api/documents/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    })
  }

  async transitionTaskState(taskId: number | string, request: StateTransitionRequest): Promise<Task> {
    return this.request<Task>(`/api/tasks/${taskId}/state-transition`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getTaskBranchInfo(taskId: number | string): Promise<TaskBranchInfo> {
    return this.request<TaskBranchInfo>(`/api/tasks/${taskId}/branch-info`)
  }

  async getTaskDiff(taskId: number | string, view: string): Promise<TaskDiffResponse> {
    return this.request<TaskDiffResponse>(`/api/tasks/${taskId}/diff?view=${encodeURIComponent(view)}`)
  }

  // Unified Conversation API
  async getConversations(): Promise<ConversationResponse[]> {
    return this.request<ConversationResponse[]>('/api/conversations')
  }

  async getConversation(conversationId: number | string): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(`/api/conversations/${conversationId}`)
  }

  async getConversationMessages(conversationId: number | string): Promise<ConversationEvent[]> {
    return this.request<ConversationEvent[]>(`/api/conversations/${conversationId}/messages`)
  }

  async *streamConversationMessage(
    conversationId: number | string,
    request: UserPrompt,
  ): AsyncGenerator<ConversationEvent> {
    await this.request<{ conversation_id: number }>(`/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
    yield* createWebSocketEventStream(Number(conversationId))
  }

  async *streamApproveConversationTools(
    conversationId: number | string,
    request: ToolApprovalRequest,
  ): AsyncGenerator<ConversationEvent> {
    await this.request<{ conversation_id: number }>(`/api/conversations/${conversationId}/approve-tools`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
    yield* createWebSocketEventStream(Number(conversationId))
  }

  async interruptConversation(conversationId: number | string): Promise<void> {
    await this.request<void>(`/api/conversations/${conversationId}/interrupt`, {
      method: 'POST',
    })
  }

  async resetConversation(conversationId: number | string): Promise<{ new_conversation_id: number; message: string }> {
    return this.request<{ new_conversation_id: number; message: string }>(`/api/conversations/${conversationId}/reset`, {
      method: 'POST',
    })
  }

  async getProjectConversations(projectId: number | string): Promise<ConversationResponse[]> {
    return this.request<ConversationResponse[]>(`/api/projects/${projectId}/conversations`)
  }

  async createProjectConversation(projectId: number | string): Promise<CreateConversationResponse> {
    return this.request<CreateConversationResponse>(`/api/projects/${projectId}/conversations`, {
      method: 'POST',
    })
  }

  async updateConversationTitle(conversationId: number | string, title: string): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(`/api/conversations/${conversationId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    })
  }

  async deleteConversation(conversationId: number | string): Promise<void> {
    return this.request<void>(`/api/conversations/${conversationId}`, {
      method: 'DELETE',
    })
  }

  async getConversationTodos(conversationId: number | string): Promise<TodoItem[]> {
    return this.request<TodoItem[]>(`/api/conversations/${conversationId}/todos`)
  }

  async getConversationAgentConfig(conversationId: number | string): Promise<AgentConfigResponse> {
    return this.request<AgentConfigResponse>(`/api/conversations/${conversationId}/agent-config`)
  }

  async executeWorkflowAction(
    taskId: number | string,
    request: PromptActionRequest,
  ): Promise<{ conversation_id?: number; status?: string; prompt?: string }> {
    return this.request<{ conversation_id?: number; status?: string; prompt?: string }>(
      `/api/tasks/${taskId}/workflow-action`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      },
    )
  }

  // Settings
  async getIntegrations(): Promise<Integration[]> {
    return this.request<Integration[]>('/api/settings/integrations')
  }

  async toggleIntegration(id: string): Promise<Integration> {
    return this.request<Integration>(`/api/settings/integrations/${id}/toggle`, {
      method: 'POST',
    })
  }

  async getLLMProviders(): Promise<LLMProvider[]> {
    return this.request<LLMProvider[]>('/api/settings/llm-providers')
  }

  async toggleLLMProvider(id: string): Promise<LLMProvider> {
    return this.request<LLMProvider>(`/api/settings/llm-providers/${id}/toggle`, {
      method: 'POST',
    })
  }

  // Custom Fields
  async getCustomFieldDefinitions(entityType?: CustomFieldEntityType): Promise<CustomFieldDefinition[]> {
    const params = entityType ? `?entity_type=${entityType}` : ''
    return this.request<CustomFieldDefinition[]>(`/api/custom-fields/${params}`)
  }

  async createCustomFieldDefinition(field: CustomFieldCreate): Promise<CustomFieldDefinition> {
    return this.request<CustomFieldDefinition>('/api/custom-fields/', {
      method: 'POST',
      body: JSON.stringify(field),
    })
  }

  async updateCustomFieldDefinition(fieldId: number, field: CustomFieldUpdate): Promise<CustomFieldDefinition> {
    return this.request<CustomFieldDefinition>(`/api/custom-fields/${fieldId}`, {
      method: 'PATCH',
      body: JSON.stringify(field),
    })
  }

  async deleteCustomFieldDefinition(fieldId: number): Promise<{ message: string; success: boolean }> {
    return this.request<{ message: string; success: boolean }>(`/api/custom-fields/${fieldId}`, {
      method: 'DELETE',
    })
  }

  // Configuration Management
  async listConfigurations(prefix: string): Promise<ConfigurationDetailResponse[]> {
    return this.request<ConfigurationDetailResponse[]>(`/api/configurations?prefix=${encodeURIComponent(prefix)}`)
  }
  
  async getConfigurationDetail(configKey: string): Promise<ConfigurationDetailResponse> {
    return this.request<ConfigurationDetailResponse>(`/api/configurations/${configKey}/detail`)
  }

  async updateConfigurationFields(configKey: string, fieldUpdates: Record<string, unknown>): Promise<ConfigurationDetailResponse> {
    return this.request<ConfigurationDetailResponse>(`/api/configurations/${configKey}/fields`, {
      method: 'PATCH',
      body: JSON.stringify(fieldUpdates),
    })
  }

  async testIntegrationConnection(integrationType: string): Promise<IntegrationTestResponse> {
    return this.request<IntegrationTestResponse>(`/api/settings/integrations/${integrationType}/test`, {
      method: 'POST',
    })
  }

  async getAgentConfiguration(agentRole: string): Promise<AgentConfigurationResponse> {
    return this.request<AgentConfigurationResponse>(`/api/agents/${agentRole}/configuration`)
  }

  async updateAgentConfiguration(agentRole: string, request: UpdateAgentConfigurationRequest): Promise<AgentConfigurationResponse> {
    return this.request<AgentConfigurationResponse>(`/api/agents/${agentRole}/configuration`, {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  async getAvailableModelsByEngine(): Promise<AvailableModelsByEngineResponse> {
    return this.request<AvailableModelsByEngineResponse>('/api/agents/available-models')
  }

  async getAgentRoleTools(agentRole: string): Promise<AgentRoleToolsResponse> {
    return this.request<AgentRoleToolsResponse>(`/api/agents/${agentRole}/tools`)
  }

  async addAgentRoleTool(agentRole: string, toolId: number): Promise<void> {
    await this.request<{ status: string }>(`/api/agents/${agentRole}/tools`, {
      method: 'POST',
      body: JSON.stringify({ tool_id: toolId }),
    })
  }

  async removeAgentRoleTool(agentRole: string, toolId: number): Promise<void> {
    await this.request<{ status: string }>(`/api/agents/${agentRole}/tools/${toolId}`, {
      method: 'DELETE',
    })
  }

  async getAvailableMCPTools(): Promise<MCPToolSummary[]> {
    return this.request<MCPToolSummary[]>('/api/agents/available-mcp-tools')
  }

  async updateConversationModel(conversationId: number | string, request: UpdateConversationModelRequest): Promise<{ conversation_id: number; agent_role: string; engine: string; model_id: string; updated_at: string }> {
    return this.request<{ conversation_id: number; agent_role: string; engine: string; model_id: string; updated_at: string }>(`/api/conversations/${conversationId}/model`, {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  }

  // Codebases
  async getCodebases(): Promise<Codebase[]> {
    return this.request<Codebase[]>('/api/codebases')
  }

  async createCodebase(codebase: CodebaseCreate): Promise<Codebase> {
    return this.request<Codebase>('/api/codebases', {
      method: 'POST',
      body: JSON.stringify(codebase),
    })
  }

  async getCodebase(id: number | string): Promise<Codebase> {
    return this.request<Codebase>(`/api/codebases/${id}`)
  }

  async updateCodebase(id: number | string, codebase: Partial<Codebase>): Promise<Codebase> {
    return this.request<Codebase>(`/api/codebases/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(codebase),
    })
  }

  async deleteCodebase(id: number | string): Promise<void> {
    return this.request<void>(`/api/codebases/${id}`, { method: 'DELETE' })
  }

  // Architecture operations
  async getArchitectureDocument(codebaseId: number | string): Promise<ArchitectureDocument> {
    return this.request<ArchitectureDocument>(`/api/codebases/${codebaseId}/architecture_document/`)
  }

  // New update endpoint
  async updateArchitectureDocument(
    codebaseId: number | string, 
    request: ArchitectureUpdateRequest
  ): Promise<ArchitectureUpdateResponse> {
    return this.request<ArchitectureUpdateResponse>(
      `/api/codebases/${codebaseId}/architecture_document/`,
      {
        method: 'PUT',
        body: JSON.stringify(request),
      }
    )
  }

  async generateArchitecture(
    codebaseId: number | string,
    options: ArchitectureGenerationRequest = {}
  ): Promise<ArchitectureGenerationResponse> {
    return this.request<ArchitectureGenerationResponse>(
      `/api/codebases/${codebaseId}/architecture_document/generate`,
      {
        method: 'POST',
        body: JSON.stringify(options),
      }
    )
  }

  // Git and Worktree Management
  async getTaskGitStatus(taskId: number | string): Promise<TaskGitStatus> {
    return this.request<TaskGitStatus>(`/api/tasks/${taskId}/git-status`)
  }

  async getTaskPRStatus(taskId: number | string): Promise<GitHubPRStatusResponse> {
    return this.request<GitHubPRStatusResponse>(`/api/tasks/${taskId}/pr-status`)
  }

  async getTaskPRFeedback(taskId: number | string): Promise<PRFeedbackResponse> {
    return this.request<PRFeedbackResponse>(`/api/tasks/${taskId}/pr-feedback`)
  }

  async mergeTaskBranch(taskId: number | string, request: MergeBranchRequest): Promise<MergeBranchResponse> {
    return this.request<MergeBranchResponse>(`/api/tasks/${taskId}/merge-branch`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async deleteTaskBranch(taskId: number | string, force: boolean = false): Promise<void> {
    return this.request<void>(`/api/tasks/${taskId}/branch?force=${force}`, {
      method: 'DELETE',
    })
  }

  async abortTaskRebase(taskId: number | string): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(`/api/tasks/${taskId}/abort-rebase`, {
      method: 'POST',
    })
  }

  async createTaskBranch(taskId: number | string): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(`/api/tasks/${taskId}/create-branch`, {
      method: 'POST',
    })
  }

  async getWorktreePoolStatus(codebaseId: number | string): Promise<WorktreePoolStatus> {
    return this.request<WorktreePoolStatus>(`/api/codebases/${codebaseId}/worktree-pool`)
  }

  async deleteWorktreeSlot(slotId: number | string, force: boolean = false): Promise<void> {
    return this.request<void>(`/api/worktree-slots/${slotId}?force=${force}`, {
      method: 'DELETE',
    })
  }

  async allocateWorkspaceForTask(taskId: number | string): Promise<WorkspaceAllocationResponse | AllSlotsLockedResponse> {
    return this.request<WorkspaceAllocationResponse | AllSlotsLockedResponse>(`/api/tasks/${taskId}/allocate-workspace`, {
      method: 'POST',
    })
  }

  async releaseWorktreeSlot(slotId: number | string): Promise<void> {
    return this.request<void>(`/api/worktree-slots/${slotId}/release`, {
      method: 'POST',
    })
  }

  async checkoutTaskToMain(taskId: number | string): Promise<CheckoutToMainResponse> {
    return this.request<CheckoutToMainResponse>(`/api/tasks/${taskId}/checkout-to-main`, {
      method: 'POST',
    })
  }

  // MCP Servers
  async listMCPServers(): Promise<MCPServerConfig[]> {
    return this.request<MCPServerConfig[]>('/api/mcp-servers')
  }

  async getMCPServerDetail(id: number | string): Promise<MCPServerDetail> {
    return this.request<MCPServerDetail>(`/api/mcp-servers/${id}`)
  }

  async createMCPServer(data: MCPServerConfigCreate): Promise<MCPServerConfig> {
    return this.request<MCPServerConfig>('/api/mcp-servers', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateMCPServer(id: number | string, data: MCPServerConfigUpdate): Promise<MCPServerConfig> {
    return this.request<MCPServerConfig>(`/api/mcp-servers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteMCPServer(id: number | string): Promise<void> {
    return this.request<void>(`/api/mcp-servers/${id}`, {
      method: 'DELETE',
    })
  }

  async verifyMCPServer(id: number | string): Promise<MCPServerDetail> {
    return this.request<MCPServerDetail>(`/api/mcp-servers/${id}/verify`, {
      method: 'POST',
    })
  }

  async updateMCPTool(serverId: number | string, toolId: number | string, data: MCPToolUpdate): Promise<MCPTool> {
    return this.request<MCPTool>(`/api/mcp-servers/${serverId}/tools/${toolId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async runMCPTool(serverId: number | string, toolId: number | string, data: MCPToolRunRequest): Promise<MCPToolRunResponse> {
    return this.request<MCPToolRunResponse>(`/api/mcp-servers/${serverId}/tools/${toolId}/run`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Claude Code Session Viewer
  async getClaudeCodeProjects(): Promise<ClaudeCodeProject[]> {
    return this.request<ClaudeCodeProject[]>('/api/claude-code/projects')
  }

  async getClaudeCodeSessions(encodedProjectPath: string): Promise<ClaudeCodeSession[]> {
    return this.request<ClaudeCodeSession[]>(`/api/claude-code/projects/${encodeURIComponent(encodedProjectPath)}/sessions`)
  }

  async getClaudeCodeSessionMessages(sessionId: string): Promise<ConversationEvent[]> {
    return this.request<ConversationEvent[]>(`/api/claude-code/sessions/${encodeURIComponent(sessionId)}/messages`)
  }

  async getClaudeCodeSubAgentMessages(sessionId: string, agentId: string): Promise<ConversationEvent[]> {
    return this.request<ConversationEvent[]>(
      `/api/claude-code/sessions/${encodeURIComponent(sessionId)}/subagents/${encodeURIComponent(agentId)}/messages`
    )
  }

  async locateClaudeCodeSession(sessionId: string): Promise<{ project_encoded_path: string }> {
    return this.request<{ project_encoded_path: string }>(`/api/claude-code/sessions/${encodeURIComponent(sessionId)}/locate`)
  }

  async searchClaudeCodeSessions(query: string, projectPath?: string): Promise<SessionSearchResult[]> {
    const params = new URLSearchParams({ query })
    if (projectPath) {
      params.set('project_path', projectPath)
    }
    return this.request<SessionSearchResult[]>(`/api/claude-code/sessions/search?${params.toString()}`)
  }

  // GitHub PR Status
  async getOpenPRs(): Promise<OpenPRsResponse> {
    return this.request<OpenPRsResponse>('/api/github/open-prs')
  }

  async getPRDetail(codebaseId: number, prNumber: number): Promise<PRDetailResponse> {
    return this.request<PRDetailResponse>(`/api/github/prs/${codebaseId}/${prNumber}/detail`)
  }

  // Implementation Plans
  async getImplementationPlan(taskId: number | string): Promise<ImplementationPlanResponse> {
    return this.request<ImplementationPlanResponse>(`/api/tasks/${taskId}/implementation-plan`)
  }

  async updateImplementationStep(
    taskId: number | string,
    stepNumber: number,
    data: ImplementationStepUpdate,
  ): Promise<ImplementationStepResponse> {
    return this.request<ImplementationStepResponse>(
      `/api/tasks/${taskId}/implementation-plan/steps/${stepNumber}`,
      {
        method: 'PATCH',
        body: JSON.stringify(data),
      },
    )
  }

  // Active Executions
  async getActiveExecutions(): Promise<ActiveExecutionsResponse> {
    return this.request<ActiveExecutionsResponse>('/api/executions/active')
  }

  async hasActiveExecution(conversationId: number): Promise<boolean> {
    const response = await this.getActiveExecutions()
    return response.executions.some((e) => e.conversation_id === conversationId)
  }
}

export const apiClient = new ApiClient()