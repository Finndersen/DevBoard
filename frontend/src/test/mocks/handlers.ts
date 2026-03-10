import { http, HttpResponse } from 'msw'
import type { Project, Task, ConfigurationDetailResponse, IntegrationTestResponse, DocumentResponse } from '../../lib/api'

// Mock documents data for separate document API calls
const mockDocuments: Record<number, DocumentResponse> = {
  1: {
    id: 1,
    document_type: 'project_specification',
    content: 'Test project specification content',
    content_hash: 'proj123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  2: {
    id: 2,
    document_type: 'project_specification',
    content: 'Another test project',
    content_hash: 'def456',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
  3: {
    id: 3,
    document_type: 'task_specification',
    content: 'Test task specification content',
    content_hash: 'task123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  4: {
    id: 4,
    document_type: 'task_implementation_plan',
    content: 'Test implementation plan content',
    content_hash: 'plan123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  5: {
    id: 5,
    document_type: 'task_specification',
    content: 'Another task specification',
    content_hash: 'task456',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
  6: {
    id: 6,
    document_type: 'task_implementation_plan',
    content: 'Implementation details here',
    content_hash: 'plan456',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
}

// Mock data
const mockProjects: Project[] = [
  {
    id: 1,
    name: 'Test Project',
    specification_document_id: 1,
    description: 'A comprehensive testing platform for automated QA workflows and continuous integration pipelines',
    default_conversation_id: 1,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Another Project',
    specification_document_id: 2,
    description: 'Enterprise dashboard for real-time analytics and business intelligence reporting',
    default_conversation_id: 2,
    created_at: '2024-01-02T00:00:00Z',
  },
]

const mockTasks: Task[] = [
  {
    id: 1,
    project_id: 1,
    title: 'Test Task',
    status: 'Designing',
    codebase_id: null,
    conversation_id: 3,
    specification_document_id: 3,
    implementation_plan_document_id: null, // No implementation plan for early-stage task
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    project_id: 1,
    title: 'Another Task',
    status: 'Planning',
    codebase_id: null,
    conversation_id: 4,
    specification_document_id: 5,
    implementation_plan_document_id: 6,
    created_at: '2024-01-02T00:00:00Z',
  },
]

const mockConfigurationResponse: ConfigurationDetailResponse = {
  key: 'integration.github.main',
  fields: [
    {
      name: 'api_token',
      type: 'string',
      required: true,
      description: 'GitHub API token',
      effective_value: null,
      env_value: null,
      db_value: null,
      default_value: null,
      is_secret: true,
      env_var_name: 'GITHUB_API_TOKEN',
      is_overridden: false,
    },
    {
      name: 'base_url',
      type: 'string',
      required: false,
      description: 'GitHub API base URL',
      effective_value: 'https://api.github.com',
      env_value: null,
      db_value: null,
      default_value: 'https://api.github.com',
      is_secret: false,
      env_var_name: 'GITHUB_BASE_URL',
      is_overridden: false,
    },
  ],
  is_valid: false,
  validation_errors: ['Missing required field: api_token'],
}

export const handlers = [
  // Projects endpoints
  http.get('*/api/projects', () => {
    return HttpResponse.json(mockProjects)
  }),

  http.post('*/api/projects', async ({ request }) => {
    const newProject = await request.json() as { name: string; description: string }
    const now = new Date().toISOString()
    const project: Project = {
      id: Date.now(),
      name: newProject.name,
      description: newProject.description,
      specification_document_id: Date.now() + 1,
      default_conversation_id: null,
      created_at: now,
    }
    return HttpResponse.json(project)
  }),

  // Documents endpoint
  http.get('*/api/documents/:id', ({ params }) => {
    const docId = Number(params.id)
    const doc = mockDocuments[docId]
    if (doc) {
      return HttpResponse.json(doc)
    }
    return new HttpResponse(null, { status: 404 })
  }),

  http.get('*/api/projects/:id', ({ params }) => {
    const project = mockProjects.find(p => p.id === Number(params.id))
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    return HttpResponse.json(project)
  }),

  http.put('*/api/projects/:id', async ({ params, request }) => {
    const updates = await request.json() as Partial<Project>
    const project = mockProjects.find(p => p.id === Number(params.id))
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    const updatedProject = { ...project, ...updates }
    return HttpResponse.json(updatedProject)
  }),

  // Tasks endpoints
  http.get('*/api/projects/:projectId/tasks', ({ params }) => {
    const projectTasks = mockTasks.filter(t => t.project_id === Number(params.projectId))
    return HttpResponse.json(projectTasks)
  }),

  http.post('*/api/projects/:projectId/tasks', async ({ params, request }) => {
    const newTask = await request.json() as Omit<Task, 'id' | 'project_id' | 'created_at'>
    const task: Task = {
      ...newTask,
      id: Date.now(),
      project_id: Number(params.projectId),
      created_at: new Date().toISOString(),
    }
    return HttpResponse.json(task)
  }),

  http.get('*/api/tasks/:id', ({ params }) => {
    const task = mockTasks.find(t => t.id === Number(params.id))
    if (!task) {
      return new HttpResponse(null, { status: 404 })
    }
    return HttpResponse.json(task)
  }),

  http.patch('*/api/tasks/:id', async ({ params, request }) => {
    const updates = await request.json() as Partial<Task>
    const task = mockTasks.find(t => t.id === Number(params.id))
    if (!task) {
      return new HttpResponse(null, { status: 404 })
    }
    const updatedTask = { ...task, ...updates }
    return HttpResponse.json(updatedTask)
  }),

  // Configuration endpoints
  http.get('*/api/configurations', ({ request }) => {
    const url = new URL(request.url)
    const prefix = url.searchParams.get('prefix')
    
    // Return list of configurations with full details
    const configs = [
      { ...mockConfigurationResponse, key: 'integration.github.main', is_valid: true },
      { ...mockConfigurationResponse, key: 'integration.jira.main', is_valid: false },
      { ...mockConfigurationResponse, key: 'integration.slack.main', is_valid: true },
      { ...mockConfigurationResponse, key: 'llm.openai.main', is_valid: true },
      { ...mockConfigurationResponse, key: 'llm.anthropic.main', is_valid: false },
      { ...mockConfigurationResponse, key: 'llm.google.main', is_valid: true },
    ]
    
    if (prefix) {
      return HttpResponse.json(configs.filter(c => c.key.startsWith(prefix)))
    }
    return HttpResponse.json(configs)
  }),

  http.get('*/api/configurations/:configKey/detail', ({ params }) => {
    // Return different mock data based on config key
    const configKey = params.configKey as string
    return HttpResponse.json({
      ...mockConfigurationResponse,
      key: configKey,
    })
  }),

  http.patch('*/api/configurations/:configKey/fields', async ({ params, request }) => {
    await request.json() // Consume request body
    return HttpResponse.json({
      ...mockConfigurationResponse,
      key: params.configKey as string,
      is_valid: true,
      validation_errors: [],
    })
  }),

  // Integration test endpoint
  http.post('*/api/settings/integrations/:integrationType/test', () => {
    const response: IntegrationTestResponse = {
      success: true,
    }
    return HttpResponse.json(response)
  }),

  // Project Q&A endpoints
  http.get('*/api/projects/:projectId/qa/history', () => {
    return HttpResponse.json([
      {
        id: '1',
        content: 'What is the current status?',
        role: 'user' as const,
        timestamp: new Date().toISOString(),
      },
      {
        id: '2',
        content: 'The project is currently in active development.',
        role: 'assistant' as const,
        timestamp: new Date().toISOString(),
      },
    ])
  }),

  http.post('*/api/projects/:projectId/qa/ask', async ({ request }) => {
    const { message } = await request.json() as { message: string }
    return HttpResponse.json({
      response: `This is a mock response to: ${message}`,
    })
  }),

  // Unified conversation endpoints
  http.get('*/api/conversations/:conversationId', ({ params }) => {
    const conversationId = Number(params.conversationId)
    // Map conversation IDs to appropriate agent roles
    // conversation_id 1 = project conversation
    // conversation_id 3 = task conversation (task_planning is the default task role)
    const agentRole = conversationId === 3 ? 'task_planning' : 'project'

    return HttpResponse.json({
      id: conversationId,
      parent_entity_type: conversationId === 3 ? 'task' : 'project',
      parent_entity_id: 1,
      agent_role: agentRole,
      engine: 'internal',
      model_id: 'openai:gpt-4',
      is_active: true,
      created_at: new Date().toISOString(),
    })
  }),

  http.get('*/api/conversations/:conversationId/messages', () => {
    return HttpResponse.json([])
  }),

  http.post('*/api/conversations/:conversationId/messages', async ({ request }) => {
    const { message } = await request.json() as { message: string }
    return HttpResponse.json({
      type: 'message',
      message: {
        id: Date.now(),
        role: 'agent',
        text_content: `Mock response to: ${message}`,
        timestamp: new Date().toISOString(),
      },
      tool_requests: null,
    })
  }),

  http.post('*/api/conversations/:conversationId/approve-tools', () => {
    return HttpResponse.json({
      type: 'message',
      message: {
        id: Date.now(),
        role: 'agent',
        text_content: 'Tools approved and executed successfully.',
        timestamp: new Date().toISOString(),
      },
      tool_requests: null,
    })
  }),

  http.delete('*/api/conversations/:conversationId/messages', () => {
    return HttpResponse.json({
      success: true,
      message: 'Conversation history cleared successfully',
    })
  }),

  http.put('*/api/conversations/:conversationId/model', async ({ params, request }) => {
    const body = await request.json() as { model_id: string }
    return HttpResponse.json({
      conversation_id: Number(params.conversationId),
      agent_role: 'project',
      engine: 'internal',
      model_id: body.model_id,
      updated_at: new Date().toISOString(),
    })
  }),

  // Agent configuration endpoints
  http.get('*/api/agents/:agentRole/configuration', () => {
    return HttpResponse.json({
      agent_role: 'project',
      config: {
        engine: 'internal',
        model_id: 'openai:gpt-4'
      },
      available_engines: [
        {
          engine: 'internal',
          display_name: 'Internal',
          description: 'Internal agent framework'
        }
      ]
    })
  }),

  http.put('*/api/agents/:agentRole/configuration', async ({ request }) => {
    const config = await request.json() as { engine: string; model_id: string }
    return HttpResponse.json({
      agent_role: 'project',
      config: {
        engine: config.engine,
        model_id: config.model_id
      },
      available_engines: [
        {
          engine: 'internal',
          display_name: 'Internal',
          description: 'Internal agent framework'
        }
      ]
    })
  }),

  http.get('*/api/agents/available-models', () => {
    return HttpResponse.json({
      models_by_engine: {
        'internal': [
          { id: 'openai:gpt-4', name: 'OpenAI GPT-4', provider: 'openai', model_type: 'standard' },
          { id: 'openai:gpt-3.5-turbo', name: 'OpenAI GPT-3.5 Turbo', provider: 'openai', model_type: 'fast' },
          { id: 'anthropic:claude-sonnet-4.5', name: 'Claude Sonnet 4.5', provider: 'anthropic', model_type: 'standard' },
        ],
        'claude_code': [
          { id: 'anthropic:claude-sonnet-4.5', name: 'Claude Sonnet 4.5', provider: 'anthropic', model_type: 'standard' },
          { id: 'anthropic:claude-opus-4.1', name: 'Claude Opus 4.1', provider: 'anthropic', model_type: 'advanced' },
        ],
        'gemini_cli': [
          { id: 'google:gemini-2.5-pro', name: 'Gemini 2.5 Pro', provider: 'google', model_type: 'standard' },
          { id: 'google:gemini-2.5-flash', name: 'Gemini 2.5 Flash', provider: 'google', model_type: 'fast' },
        ]
      }
    })
  }),

  // Codebases endpoints
  http.get('*/api/codebases', () => {
    return HttpResponse.json([
      {
        id: 1,
        name: 'Test Codebase 1',
        description: 'First test codebase',
        local_path: '/path/to/codebase1',
        repository_url: 'https://github.com/test/repo1',
      },
      {
        id: 2,
        name: 'Test Codebase 2',
        description: 'Second test codebase',
        local_path: '/path/to/codebase2',
        repository_url: 'https://github.com/test/repo2',
      },
    ])
  }),

  // Architecture document endpoints - let tests set their own handlers
]