"""Registry for workflow actions using the generic Registry pattern."""

from devboard.core.registry import Registry
from devboard.workflow_actions.base import TaskWorkflowAction
from devboard.workflow_actions.task_workflows import (
    ApproveAndCreatePRAction,
    ApproveAndMergeAction,
    ArchiveTaskAction,
    BeginImplementationAction,
    CreateImplementationPlanAction,
    FinaliseAction,
    MergeAndFinaliseAction,
    RebaseTaskBranchAction,
)

# List of all workflow action classes
_workflow_actions: list[type[TaskWorkflowAction]] = [
    CreateImplementationPlanAction,
    BeginImplementationAction,
    RebaseTaskBranchAction,
    ApproveAndMergeAction,
    ApproveAndCreatePRAction,
    MergeAndFinaliseAction,
    FinaliseAction,
    ArchiveTaskAction,
]

# Registry of all workflow action definitions using the generic Registry pattern
workflow_action_registry = Registry[type[TaskWorkflowAction]](
    items=_workflow_actions,
    key_attr="KEY",
)
