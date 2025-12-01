"""Pydantic schemas package."""

from .codebase import (
    CodebaseBase,
    CodebaseCreate,
    CodebaseResponse,
    CodebaseUpdate,
)
from .common import DeleteResponse
from .conversation import ConversationResponse
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
    CommitMetadata,
    FileDiff,
    MergeBranchRequest,
    MergeBranchResponse,
    StateTransitionRequest,
    TaskBase,
    TaskBranchInfo,
    TaskCreate,
    TaskCreateNested,
    TaskDiffResponse,
    TaskGitStatusResponse,
    TaskResponse,
    TaskUpdate,
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
    # Codebase
    "CodebaseBase",
    "CodebaseCreate",
    "CodebaseResponse",
    "CodebaseUpdate",
    # Common
    "DeleteResponse",
    # Conversation
    "ConversationResponse",
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
    "CommitMetadata",
    "DocumentEdit",
    "FileDiff",
    "MergeBranchRequest",
    "MergeBranchResponse",
    "StateTransitionRequest",
    "TaskBase",
    "TaskBranchInfo",
    "TaskCreate",
    "TaskCreateNested",
    "TaskDiffResponse",
    "TaskGitStatusResponse",
    "TaskResponse",
    "TaskUpdate",
    # Worktree
    "CreateWorktreeSlotRequest",
    "ReconcileWorktreePoolResponse",
    "WorkspaceAllocationErrorResponse",
    "WorkspaceAllocationResponse",
    "WorktreePoolStatusResponse",
    "WorktreeSlotResponse",
    "WorktreeSlotWithTaskInfo",
]
