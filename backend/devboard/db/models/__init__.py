"""Database models package."""

from .base import Base
from .codebase import BranchHandling, Codebase, MergeMethod, MergeStrategy
from .configuration import Configuration, ContextProviderResource
from .conversation import Conversation, ParentEntityType
from .document import Document, DocumentType
from .messages import ConversationMessage, MessageType
from .oauth import (
    HttpMCPConfig,
    MCPServerConfig,
    MCPServerType,
    OAuthClientInfo,
    OAuthProvider,
    OAuthProviderType,
    OAuthToken,
    PendingOAuthAuthorization,
    StdioMCPConfig,
)
from .project import Project
from .task import Task, TaskStatus
from .worktree_slot import WorktreeSlot

__all__ = [
    "Base",
    "BranchHandling",
    "Codebase",
    "Configuration",
    "ContextProviderResource",
    "Conversation",
    "ConversationMessage",
    "Document",
    "DocumentType",
    "HttpMCPConfig",
    "MCPServerConfig",
    "MCPServerType",
    "MergeMethod",
    "MergeStrategy",  # Deprecated alias for MergeMethod
    "MessageType",
    "OAuthClientInfo",
    "OAuthProvider",
    "OAuthProviderType",
    "OAuthToken",
    "ParentEntityType",
    "PendingOAuthAuthorization",
    "Project",
    "StdioMCPConfig",
    "Task",
    "TaskStatus",
    "WorktreeSlot",
]
