"""Pydantic schemas package."""

from .codebase import (
    ArchitectureDocumentResponse,
    ArchitectureGenerationResponse,
    ArchitectureUpdateRequest,
    ArchitectureUpdateResponse,
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
    FileDiff,
    StateTransitionRequest,
    TaskBase,
    TaskCreate,
    TaskCreateNested,
    TaskDiffResponse,
    TaskResponse,
    TaskUpdate,
)

__all__ = [
    # Codebase
    "ArchitectureDocumentResponse",
    "ArchitectureGenerationResponse",
    "ArchitectureUpdateRequest",
    "ArchitectureUpdateResponse",
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
    "DocumentEdit",
    "FileDiff",
    "StateTransitionRequest",
    "TaskBase",
    "TaskCreate",
    "TaskCreateNested",
    "TaskDiffResponse",
    "TaskResponse",
    "TaskUpdate",
]
