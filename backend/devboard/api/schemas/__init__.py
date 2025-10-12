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
from .configuration import (
    ConfigurationDetailResponse,
    ConfigurationFieldInfo,
)
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
    ModelInfo,
    UpdateAgentConfigurationRequest,
    UpdateAgentModelRequest,
    UpdateConversationModelRequest,
)
from .project import ProjectBase, ProjectCreate, ProjectResponse, ProjectUpdate
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
    StateTransitionRequest,
    TaskBase,
    TaskCreate,
    TaskCreateNested,
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
    "ConfigurationDetailResponse",
    "ConfigurationFieldInfo",
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
    "ModelInfo",
    "UpdateAgentConfigurationRequest",
    "UpdateAgentModelRequest",
    "UpdateConversationModelRequest",
    # Project
    "ProjectBase",
    "ProjectCreate",
    "ProjectResponse",
    "ProjectUpdate",
    # Task
    "DocumentEdit",
    "StateTransitionRequest",
    "TaskBase",
    "TaskCreate",
    "TaskCreateNested",
    "TaskResponse",
    "TaskUpdate",
]
