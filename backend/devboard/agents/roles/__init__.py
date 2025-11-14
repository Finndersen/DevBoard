"""Agent roles package.

Individual role classes and types should be imported directly:
- from devboard.agents.role_types import AgentRoleType
- from devboard.agents.roles.base import Role
- from devboard.agents.roles.codebase_investigation import CodebaseInvestigationRole
- from devboard.agents.roles.project_qa import ProjectQARole
- from devboard.agents.roles.task_specification import TaskSpecificationRole
- from devboard.agents.roles.task_planning import TaskPlanningRole
- from devboard.agents.roles.task_implementation import TaskImplementationRole

WARNING: Do not import role classes in this __init__.py file as it creates circular imports.
The roles package should only contain documentation, not actual imports.
"""
