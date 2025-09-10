from enum import Enum


class AgentType(Enum):
    """Available agent types in the system."""

    PROJECT = "project"
    # TODO: Keep these two task agents seperate or combine?
    TASK_SPECIFICATION = "task_specification"
    TASK_PLANNING = "task_planning"
    TASK_IMPLEMENTATION = "task_implementation"
    INVESTIGATION = "investigation"
