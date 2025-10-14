from devboard.db.models import Task

PLANNING_SYSTEM_PROMPT = """
You are a Task Planning Assistant for DevBoard, helping developers create detailed implementation plans.

Your role is to help iteratively improve both the Task Specification and Implementation Plan based on:
- User input and technical requirements
- Context from the project (GitHub, Jira, Slack, Codebase)
- Technical analysis and architecture understanding
- Best practices for implementation planning

DOCUMENT EDITING RULES:
1. Make precise find-replace edits using DocumentEdit objects
2. Use exact text matches for 'find' - the text must exist exactly as written
3. Preserve markdown formatting and structure
4. When adding new content, find a logical insertion point and replace with expanded content
5. For placeholder text like "[High-level approach]", replace the entire placeholder

CURRENT TASK STATE: Planning
AVAILABLE ACTIONS:
- Edit both Task Specification and Implementation Plan documents
- Research project context and codebase for technical details
- Suggest transition to Implementing state when plan is complete

Your responses should be technical, detailed, and focused on creating actionable implementation steps.
"""


def build_task_planning_context(task: Task) -> str:
    """Build context for task planning agent.

    Includes task metadata, project specification, task specification,
    and implementation plan documents.

    Note: Requires task to be loaded within an active SQLAlchemy session,
    as it will lazy-load the project relationship if needed.

    Args:
        task: Task instance with eager-loaded documents

    Returns:
        Formatted context string
    """
    return f"""
TASK NAME: {task.title}
TASK STATUS: {task.status.value}

PROJECT SPECIFICATION:
```markdown
{task.project.specification.content or "<EMPTY>"}
```

TASK SPECIFICATION DOCUMENT:
```markdown
{task.specification.content or "<EMPTY>"}
```

TASK IMPLEMENTATION PLAN DOCUMENT:
```markdown
{task.implementation_plan.content or "<EMPTY>"}
```
"""
