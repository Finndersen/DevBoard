from enum import StrEnum


class AgentRoleType(StrEnum):
    """Available agent roles in the system.

    Each role represents a specific responsibility or function that an agent
    can fulfill, such as project management, task planning, or implementation.
    """

    PROJECT = "project"
    # TODO: Keep these two task agents seperate or combine?
    TASK_SPECIFICATION = "task_specification"
    TASK_PLANNING = "task_planning"
    TASK_IMPLEMENTATION = "task_implementation"
    INVESTIGATION = "investigation"
    CONVERSATION_EVALUATOR = "conversation_evaluator"
