"""Agent role type enumeration.

This module contains the AgentRoleType enum, separated to avoid circular imports.
"""

from enum import StrEnum


class AgentRoleType(StrEnum):
    """Available agent roles in the system.

    Each role represents a specific responsibility or function that an agent
    can fulfill, such as project management, task planning, or implementation.
    """

    PROJECT = "project"
    TASK_PLANNING = "task_planning"
    TASK_IMPLEMENTATION = "task_implementation"
    TASK_PR_REVIEW = "task_pr_review"
    TASK_FINALISATION = "task_finalisation"
    INVESTIGATION = "investigation"
    CODE_REVIEW = "code_review"
    STEP_EXECUTION = "step_execution"
    BACKGROUND_AGENT = "background_agent"
