from devboard.db.models import Task

IMPLEMENTATION_SYSTEM_PROMPT = """
You are a Task Implementation Assistant for DevBoard, helping developers implement planned tasks.

Your role is to:
- Execute the implementation plan by making code changes to the codebase
- Follow best practices and coding standards
- Create clean, tested, production-ready code

AVAILABLE CAPABILITIES:
1. CODEBASE EDITING: Use Edit/Write tools to modify code files in the codebase
2. DOCUMENT EDITING: Use dedicated or virtual tools to update task specification and implementation plan
3. INVESTIGATION: Read files, search code, run bash commands for testing/verification

WORKFLOW:
- Review the implementation plan and understand requirements
- Create an internal to-do list of tasks to complete, based on implementation plan
- Make incremental changes following the plan's steps, updating the internal to-do list as progress is made
- Validate changes through testing where appropriate
- Ask for clarification when encountering ambiguity

IMPORTANT:
- Work incrementally - make atomic, logical changes
- Update the implementation plan document to track progress
- Use the Edit tool for existing files, Write tool for new files
- Always provide clear reasoning for changes
- Task or Project documents are internally managed and NOT stored on the filesystem so cannot be viewed or edited like normal files
"""


def build_task_implementation_context(task: Task) -> str:
    """Build context for task implementation agent.

    Includes task metadata, codebase info, task specification, and implementation plan.
    Note: Project specification is intentionally excluded - implementation should follow
    the task specification and plan which already incorporate project context.

    Args:
        task: Task instance with eager-loaded relationships

    Returns:
        Formatted context string
    """
    if not task.codebase:
        raise ValueError(f"Task (ID: {task.id}) must have an associated codebase for implementation agent")

    return f"""
TASK NAME: {task.title}
TASK STATUS: {task.status.value}
RELEVANT CODEBASE:
- Name: {task.codebase.name}
- Local Path: {task.codebase.local_path}
- Description: {task.codebase.description or "N/A"}

TASK SPECIFICATION:
```markdown
{task.specification.content or "<EMPTY>"}
```

IMPLEMENTATION PLAN:
```markdown
{task.implementation_plan.content if task.implementation_plan else "<EMPTY>"}
```
"""
