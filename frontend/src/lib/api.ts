import { StreamParser } from './streaming'

export interface Project {
  id: number
  name: string
  specification_document_id: number
  description: string
  default_conversation_id: number | null
  created_at: string
}

export interface WorkflowActionInfo {
  key: string
}

export interface Task {
  id: number
  title: string
  status: string
  project_id: number
  codebase_id: number
  conversation_id: number
  created_at: string
  specification_document_id: number
  implementation_plan_document_id: number | null
  change_summary_document_id: number | null
  custom_fields: Record<string, unknown> | null
  available_workflow_actions: WorkflowActionInfo[]
}

export interface TaskListItem {
  id: number
  title: string
  project_id: number
  project_name: string
  codebase_id: number
  status: string
  created_at: string
}

export interface GitHubPRStatusResponse {
  merged: boolean
  mergeable: boolean | null
  mergeable_state: string
  state: string
  review_comments_count: number
  checks_status: string | null
  pr_url: string
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

export type ConversationEventType = 'message' | 'tool_call' | 'tool_result' | 'tool_call_request' | 'system' | 'meta_message'

export type MetaMessageType = 'compact_summary' | 'skill_content'

export interface MetaMessage {
  event_type: 'meta_message'
  meta_type: MetaMessageType
  text_content: string
  timestamp: string
  uuid?: string
}

export type SystemEventType = 'task_updated' | 'conversation_updated' | 'workspace_allocate' | 'workspace_branch_checkout' | 'workspace_create' | 'workspace_setup' | 'stream_error' | 'stream_interrupted' | 'branch_rebased' | 'stash_apply_conflict' | 'session_expired' | 'compacting_conversation'

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

// Union type for all conversation events
export type ConversationEvent = ConversationMessage | ToolCall | ToolResult | ToolCallRequest | SystemEvent | MetaMessage

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
  status: 'locked' | 'available'
  current_branch: string | null
  last_used_at: string | null
  locked_by_task: TaskInfoSimple | null
  last_used_by_task: TaskInfoSimple | null
  locked_at: string | null
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
  type: 'string' | 'boolean' | 'integer' | 'number'
  required: boolean
  description?: string
  env_value?: unknown
  db_value?: unknown
  default_value?: unknown
  is_secret: boolean
  env_var_name?: string
  is_overridden: boolean
  effective_value: unknown
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
  model_type: 'reasoning' | 'fast'
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

export interface MCPServerDetail {
  id: number
  name: string
  server_type: MCPServerType
  config_json: MCPConfigJson
  last_verified_at: string | null
  last_verified_success: boolean | null
  last_verified_error: string | null
  tools: MCPTool[]
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
  created_at: string
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
  last_cost: number | null
  last_lines_added: number | null
  last_lines_removed: number | null
  session_count: number
}

export interface ClaudeCodeSession {
  session_id: string
  label: string
  last_activity: string
  file_size: number
  is_empty: boolean
  linked_session_id: string | null
  session_role: 'plan' | 'implementation' | null
}

export interface SessionSearchResult {
  session_id: string
  project_encoded_path: string
  line_number: number
  line_content: string
  message_uuid: string | null
  text_snippet: string | null
}

export class ApiClient {
  private readonly baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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
  async getConversation(conversationId: number | string): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(`/api/conversations/${conversationId}`)
  }

  async getConversationMessages(conversationId: number | string): Promise<ConversationEvent[]> {
    return this.request<ConversationEvent[]>(`/api/conversations/${conversationId}/messages`)
  }

  async sendConversationMessage(conversationId: number | string, request: UserPrompt): Promise<ConversationEvent[]> {
    return this.request<ConversationEvent[]>(`/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async *streamConversationMessage(
    conversationId: number | string,
    request: UserPrompt,
    signal?: AbortSignal,
  ): AsyncGenerator<ConversationEvent> {
    yield* StreamParser.parseStream(
      `${this.baseURL}/api/conversations/${conversationId}/messages/stream`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
      },
    )
  }

  async approveConversationTools(conversationId: number | string, request: ToolApprovalRequest): Promise<ConversationEvent[]> {
    return this.request<ConversationEvent[]>(`/api/conversations/${conversationId}/approve-tools`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async *streamApproveConversationTools(
    conversationId: number | string,
    request: ToolApprovalRequest,
    signal?: AbortSignal,
  ): AsyncGenerator<ConversationEvent> {
    yield* StreamParser.parseStream(
      `${this.baseURL}/api/conversations/${conversationId}/approve-tools/stream`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
      },
    )
  }

  async resetConversation(conversationId: number | string): Promise<{ new_conversation_id: number; message: string }> {
    return this.request<{ new_conversation_id: number; message: string }>(`/api/conversations/${conversationId}/reset`, {
      method: 'POST',
    })
  }

  async getConversationTodos(conversationId: number | string): Promise<TodoItem[]> {
    return this.request<TodoItem[]>(`/api/conversations/${conversationId}/todos`)
  }

  async *streamWorkflowAction(
    taskId: number | string,
    request: PromptActionRequest,
  ): AsyncGenerator<ConversationEvent> {
    yield* StreamParser.parseStream(
      `${this.baseURL}/api/tasks/${taskId}/workflow-action`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

  async getWorktreePoolStatus(codebaseId: number | string): Promise<WorktreePoolStatus> {
    return this.request<WorktreePoolStatus>(`/api/codebases/${codebaseId}/worktree-pool`)
  }

  async deleteWorktreeSlot(slotId: number | string, force: boolean = false): Promise<void> {
    return this.request<void>(`/api/worktree-slots/${slotId}?force=${force}`, {
      method: 'DELETE',
    })
  }

  async reconcileWorktreePool(codebaseId: number | string): Promise<void> {
    return this.request<void>(`/api/codebases/${codebaseId}/worktree-pool/reconcile`, {
      method: 'POST',
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

  async searchClaudeCodeSessions(query: string, projectPath?: string): Promise<SessionSearchResult[]> {
    const params = new URLSearchParams({ query })
    if (projectPath) {
      params.set('project_path', projectPath)
    }
    return this.request<SessionSearchResult[]>(`/api/claude-code/sessions/search?${params.toString()}`)
  }
}

export const apiClient = new ApiClient()