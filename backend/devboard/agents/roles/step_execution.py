"""Step execution sub-agent role for executing individual implementation plan steps."""

from pydantic_ai import Tool

from devboard.agents.roles.base import AgentRole
from devboard.agents.roles.context_helpers import build_task_context
from devboard.db.models.implementation_plan import ImplementationStep, ImplementationStepType
from devboard.db.models.task import Task

STEP_TYPE_PREAMBLES = {
    ImplementationStepType.CODE_CHANGE: (
        "You are implementing a specific code change as part of a larger implementation plan. "
        "Focus on making the described changes cleanly and completely. "
        "Write tests for new functionality but do NOT run them — a later validation step handles that. "
        "After implementing, run fast validation checks (lint, format, typecheck) on the files you modified and fix any issues before completing the step. "
        "The relevant commands can be found in the codebase's developer context."
    ),
    ImplementationStepType.DOCUMENTATION: (
        "You are updating documentation as part of a larger implementation plan. Focus on accuracy and completeness."
    ),
    ImplementationStepType.VALIDATION: (
        "You are running the full validation suite as the final gate. "
        "Run lint/format/typecheck first as a safety net (these should already be clean from individual implementation steps), "
        "then run the full test suite. "
        "Focus primarily on test failures and integration issues. "
        "Fix any issues found, re-run to verify fixes, and report results."
    ),
}

STEP_EXECUTION_BASE_PROMPT = """You are a focused implementation sub-agent executing a specific step of the current task's implementation plan.

{type_preamble}

GUIDELINES:
- Execute the step instructions completely and accurately
- Use the implementation plan in your context to understand the full scope of work and what has been done in previous steps
- After completing the step, provide a concise outcome summary describing what was done, any issues encountered, and important notes
- Do not make changes beyond the scope of this step
"""


class StepExecutionAgentRole(AgentRole):
    """Role for executing a single implementation plan step."""

    def __init__(
        self,
        task: Task,
        step: ImplementationStep,
        working_dir: str,
    ):
        self.task = task
        self.step = step
        self._working_dir = working_dir

    def get_system_prompt(self) -> str:
        type_preamble = STEP_TYPE_PREAMBLES.get(self.step.type, STEP_TYPE_PREAMBLES[ImplementationStepType.CODE_CHANGE])
        return STEP_EXECUTION_BASE_PROMPT.format(type_preamble=type_preamble)

    def get_tools(self) -> list[Tool]:
        return []

    async def get_context_content(self) -> str:
        return build_task_context(self.task, working_dir=self._working_dir, include_step_outcomes=True)

    @property
    def allowed_builtin_tools(self) -> list[str]:
        return [
            "Read",
            "Grep",
            "Glob",
            "Edit",
            "Write",
            "Bash",
            "WebFetch",
            "WebSearch",
            "Agent",
        ]

    @property
    def include_builtin_system_prompt(self) -> bool:
        return True

    @property
    def include_claude_md(self) -> bool:
        return True
