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
    ConfigurationBase,
    ConfigurationCreate,
    ConfigurationDetailResponse,
    ConfigurationFieldInfo,
    ConfigurationResponse,
    ConfigurationUpdate,
    ContextProviderResourceBase,
    ContextProviderResourceCreate,
    ContextProviderResourceResponse,
    ContextProviderResourceUpdate,
    ProjectResourceCreate,
    ResourceResponse,
    TaskResourceCreate,
)
from .integration import (
    AgentModelInfo,
    AvailableModelsResponse,
    IntegrationTestResponse,
    ModelInfo,
)
from .project import ProjectBase, ProjectCreate, ProjectResponse, ProjectUpdate
from .document import DocumentCreate, DocumentResponse, DocumentUpdate
from .task import (
    ApplyEditsRequest,
    DocumentEdit,
    StateTransitionRequest,
    TaskBase,
    TaskConversationMessage,
    TaskCreate,
    TaskCreateNested,
    TaskPlanningRequest,
    TaskPlanningResponse,
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
    # Document
    "DocumentCreate",
    "DocumentResponse",
    "DocumentUpdate",
    # Configuration
    "ConfigurationBase",
    "ConfigurationCreate",
    "ConfigurationDetailResponse",
    "ConfigurationFieldInfo",
    "ConfigurationResponse",
    "ConfigurationUpdate",
    "ContextProviderResourceBase",
    "ContextProviderResourceCreate",
    "ContextProviderResourceResponse",
    "ContextProviderResourceUpdate",
    "ProjectResourceCreate",
    "ResourceResponse",
    "TaskResourceCreate",
    # Integration
    "AgentModelInfo",
    "AvailableModelsResponse",
    "IntegrationTestResponse",
    "ModelInfo",
    # Project
    "ProjectBase",
    "ProjectCreate",
    "ProjectResponse",
    "ProjectUpdate",
    # Task
    "ApplyEditsRequest",
    "DocumentEdit",
    "StateTransitionRequest",
    "TaskBase",
    "TaskConversationMessage",
    "TaskCreate",
    "TaskCreateNested",
    "TaskPlanningRequest",
    "TaskPlanningResponse",
    "TaskResponse",
    "TaskUpdate",
]
