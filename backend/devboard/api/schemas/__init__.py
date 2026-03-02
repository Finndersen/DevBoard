"""Pydantic schemas package."""

from .agents import (
    AddMCPToolRequest,
    AgentRoleToolsResponse,
    MCPToolSummary,
    UpdateAgentConfigurationRequestFull,
)
from .codebase import (
    CodebaseBase,
    CodebaseCreate,
    CodebaseResponse,
    CodebaseUpdate,
)
from .common import DeleteResponse
from .conversation import ConversationResponse
from .custom_field import CustomFieldCreate, CustomFieldResponse, CustomFieldUpdate
from .document import DocumentCreate, DocumentEdit, DocumentResponse, DocumentUpdate
from .integration import (
    AgentConfigurationResponse,
    AgentEngineInfo,
    AgentEngineModelConfigSchema,
    AgentModelInfo,
    AgentModelResponse,
    AvailableModelsByEngineResponse,
    AvailableModelsResponse,
    IntegrationTestResponse,
    UpdateAgentConfigurationRequest,
    UpdateAgentModelRequest,
    UpdateConversationModelRequest,
)
from .mcp import (
    MCPServerDetailResponse,
    MCPToolInfo,
    MCPToolResponse,
    MCPToolRunRequest,
    MCPToolRunResponse,
    MCPToolUpdate,
    VerifyResult,
)
from .oauth import (
    MCPServerConfigCreate,
    MCPServerConfigResponse,
    MCPServerConfigUpdate,
    OAuthCallbackError,
    OAuthCallbackQueryParams,
    OAuthCallbackResponse,
)
from .project import ProjectBase, ProjectCreate, ProjectResponse, ProjectUpdate
from .prompt_action import PromptActionRequest
from .resource import (
    ContextProviderResourceBase,
    ContextProviderResourceCreate,
    ContextProviderResourceResponse,
    ContextProviderResourceUpdate,
    ProjectResourceCreate,
    ResourceResponse,
    TaskResourceCreate,
)
from .task import (
    CheckoutToMainResponse,
    CommitMetadata,
    FileDiff,
    GitHubPRStatusResponse,
    MergeBranchRequest,
    MergeBranchResponse,
    RebaseBranchResponse,
    StateTransitionRequest,
    TaskBase,
    TaskBranchInfo,
    TaskCreate,
    TaskCreateNested,
    TaskDiffResponse,
    TaskGitStatusResponse,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
    WorkflowActionInfo,
)
from .worktree import (
    CreateWorktreeSlotRequest,
    ReconcileWorktreePoolResponse,
    WorkspaceAllocationErrorResponse,
    WorkspaceAllocationResponse,
    WorktreePoolStatusResponse,
    WorktreeSlotResponse,
    WorktreeSlotWithTaskInfo,
)

__all__ = [
    # Agents
    "AddMCPToolRequest",
    "AgentRoleToolsResponse",
    "MCPToolSummary",
    "UpdateAgentConfigurationRequestFull",
    # Codebase
    "CodebaseBase",
    "CodebaseCreate",
    "CodebaseResponse",
    "CodebaseUpdate",
    # Common
    "DeleteResponse",
    # Conversation
    "ConversationResponse",
    # Custom Field
    "CustomFieldCreate",
    "CustomFieldResponse",
    "CustomFieldUpdate",
    # Document
    "DocumentCreate",
    "DocumentResponse",
    "DocumentUpdate",
    # Configuration
    "ContextProviderResourceBase",
    "ContextProviderResourceCreate",
    "ContextProviderResourceResponse",
    "ContextProviderResourceUpdate",
    "ProjectResourceCreate",
    "ResourceResponse",
    "TaskResourceCreate",
    # Integration
    "AgentConfigurationResponse",
    "AgentEngineInfo",
    "AgentEngineModelConfigSchema",
    "AgentModelInfo",
    "AgentModelResponse",
    "AvailableModelsByEngineResponse",
    "AvailableModelsResponse",
    "IntegrationTestResponse",
    "UpdateAgentConfigurationRequest",
    "UpdateAgentModelRequest",
    "UpdateConversationModelRequest",
    # Project
    "ProjectBase",
    "ProjectCreate",
    "ProjectResponse",
    "ProjectUpdate",
    # Prompt Action
    "PromptActionRequest",
    # Task
    "CheckoutToMainResponse",
    "CommitMetadata",
    "DocumentEdit",
    "FileDiff",
    "GitHubPRStatusResponse",
    "MergeBranchRequest",
    "MergeBranchResponse",
    "RebaseBranchResponse",
    "StateTransitionRequest",
    "TaskBase",
    "TaskBranchInfo",
    "TaskCreate",
    "TaskCreateNested",
    "TaskDiffResponse",
    "TaskGitStatusResponse",
    "TaskListResponse",
    "TaskResponse",
    "TaskUpdate",
    "WorkflowActionInfo",
    # MCP
    "MCPServerConfigCreate",
    "MCPServerConfigResponse",
    "MCPServerConfigUpdate",
    "MCPServerDetailResponse",
    "MCPToolInfo",
    "MCPToolResponse",
    "MCPToolRunRequest",
    "MCPToolRunResponse",
    "MCPToolUpdate",
    "VerifyResult",
    # OAuth
    "OAuthCallbackError",
    "OAuthCallbackQueryParams",
    "OAuthCallbackResponse",
    # Worktree
    "CreateWorktreeSlotRequest",
    "ReconcileWorktreePoolResponse",
    "WorkspaceAllocationErrorResponse",
    "WorkspaceAllocationResponse",
    "WorktreePoolStatusResponse",
    "WorktreeSlotResponse",
    "WorktreeSlotWithTaskInfo",
]
