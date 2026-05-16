"""Database models package."""

from .agent_role_config import AgentRoleConfig
from .background_agent import (
    BackgroundAgent,
    BackgroundAgentEventTrigger,
    BackgroundAgentScheduleTrigger,
)
from .background_agent_run import BackgroundAgentRun, BackgroundAgentRunStatus
from .base import Base
from .claude_project import ClaudeProjectPathCache
from .codebase import BranchHandling, Codebase, MergeMethod
from .configuration import Configuration
from .conversation import Conversation
from .custom_field import CustomFieldDefinition, CustomFieldType
from .document import Document, DocumentType
from .enums import EntityType, ParentEntityType
from .implementation_plan import (
    ImplementationPlan,
    ImplementationStep,
    ImplementationStepStatus,
    ImplementationStepType,
)
from .language_model import LanguageModelDB
from .log_entry import LogEntry, LogEntrySource, LogEntryStatus
from .mcp_server import (
    HttpMCPConfig,
    MCPServerConfig,
    MCPServerType,
    MCPTool,
    StdioMCPConfig,
)
from .messages import ConversationMessage, MessageType
from .oauth import (
    OAuthClientInfo,
    OAuthProvider,
    OAuthProviderType,
    OAuthToken,
    PendingOAuthAuthorization,
)
from .project import Project
from .task import Task, TaskStatus
from .worktree_slot import WorktreeSlot

ParentEntity = Task | Project | Codebase | BackgroundAgent

__all__ = [
    "AgentRoleConfig",
    "BackgroundAgent",
    "BackgroundAgentEventTrigger",
    "BackgroundAgentRun",
    "BackgroundAgentRunStatus",
    "BackgroundAgentScheduleTrigger",
    "Base",
    "ClaudeProjectPathCache",
    "BranchHandling",
    "Codebase",
    "CustomFieldDefinition",
    "CustomFieldType",
    "Configuration",
    "Conversation",
    "ConversationMessage",
    "Document",
    "DocumentType",
    "HttpMCPConfig",
    "MCPServerConfig",
    "MCPServerType",
    "MCPTool",
    "MergeMethod",
    "MessageType",
    "OAuthClientInfo",
    "OAuthProvider",
    "OAuthProviderType",
    "OAuthToken",
    "EntityType",
    "LogEntry",
    "LogEntrySource",
    "LogEntryStatus",
    "ImplementationPlan",
    "LanguageModelDB",
    "ImplementationStep",
    "ImplementationStepStatus",
    "ImplementationStepType",
    "ParentEntity",
    "ParentEntityType",
    "PendingOAuthAuthorization",
    "Project",
    "StdioMCPConfig",
    "Task",
    "TaskStatus",
    "WorktreeSlot",
]
