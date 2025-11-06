"""Data models for conversation evaluation.

This module defines Pydantic models used for evaluating agent conversations,
including agent specifications, conversation analysis inputs, and structured
evaluation outputs with scores and improvement suggestions.
"""

import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.events import ConversationEvent
from devboard.agents.roles.types import AgentRoleType


class Priority(StrEnum):
    """Priority level for improvement suggestions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ToolSpecification(BaseModel):
    """Tool definition for evaluation.

    Represents a tool available to the agent being evaluated, including
    its name, description, parameters, and approval requirements.
    """

    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    parameters: dict[str, Any] = Field(description="Parameter schema for the tool")
    requires_approval: bool = Field(description="Whether the tool requires user approval")


class AgentSpecification(BaseModel):
    """Formatted representation of agent configuration.

    Contains all relevant information about how an agent is configured,
    including its role, system prompt, available tools, and initial context.
    This is provided to the evaluator agent for analysis.
    """

    role_type: AgentRoleType = Field(description="Type of agent role")
    system_prompt: str = Field(description="System prompt defining agent behavior")
    tools: list[ToolSpecification] = Field(description="List of tools available to the agent")
    context_summary: str = Field(description="Summary of initial context provided to agent")
    allowed_builtin_tools: list[str] = Field(
        default_factory=list, description="List of engine-specific builtin tools allowed"
    )


class ConversationAnalysis(BaseModel):
    """Formatted conversation for evaluation.

    Contains the complete conversation history along with agent configuration
    and metadata needed for evaluation. This is the primary input to the
    evaluation process.
    """

    conversation_id: int = Field(description="ID of the conversation being evaluated")
    agent_specification: AgentSpecification = Field(description="Configuration of the agent")
    engine: AgentEngine = Field(description="Engine used to execute the agent")
    model_id: str = Field(description="Model ID used for the conversation")
    events: list[ConversationEvent] = Field(description="List of conversation events in chronological order")
    started_at: datetime.datetime = Field(description="When the conversation started")
    event_count: int = Field(description="Total number of events")
    tool_call_count: int = Field(description="Total number of tool calls")


class Improvement(BaseModel):
    """Suggested improvement for agent configuration.

    Represents a specific, actionable suggestion for improving agent
    performance in a particular area.
    """

    priority: Priority = Field(description="Priority level of this improvement")
    title: str = Field(description="Brief title summarizing the improvement")
    description: str = Field(description="Detailed description of the issue and why it matters")
    suggested_changes: str = Field(description="Specific changes to make (e.g., prompt edits, tool additions)")
    expected_impact: str = Field(description="Expected improvement from implementing this change")


class Evaluation(BaseModel):
    """Individual evaluation with score, explanation, and improvements.

    Represents the evaluation of a specific aspect of agent performance
    (e.g., system prompt effectiveness, tool quality) with a score,
    detailed explanation, supporting evidence, and improvement suggestions.
    """

    score: float = Field(ge=0.0, le=10.0, description="Score from 0-10 for this aspect")
    explanation: str = Field(description="Detailed explanation of the score")
    evidence: list[str] = Field(
        default_factory=list, description="References to specific events/messages that support this evaluation"
    )
    improvements: list[Improvement] = Field(
        default_factory=list, description="Suggested improvements for this specific aspect"
    )


class PerformanceEvaluations(BaseModel):
    """Detailed performance metrics across all evaluation dimensions.

    Contains evaluations for each major aspect of agent performance.
    Each evaluation includes scores, explanations, and targeted improvements.
    """

    system_prompt_effectiveness: Evaluation = Field(
        description="How well the system prompt guides agent behavior, clarity, completeness, and handling of edge cases"
    )
    tool_specification_quality: Evaluation = Field(
        description="Quality of tool definitions including naming, descriptions, parameters, and approval settings"
    )
    context_management: Evaluation = Field(
        description="Effectiveness of initial context and context usage throughout conversation"
    )
    response_quality: Evaluation = Field(
        description="Quality of agent responses including accuracy, relevance, and helpfulness"
    )
    conversation_efficiency: Evaluation = Field(
        description="Efficiency of conversation flow, appropriate tool usage, and achieving goals with minimal steps"
    )


class ConversationEvaluation(BaseModel):
    """Structured evaluation result for a conversation.

    The complete output from evaluating an agent conversation, including
    an overall rating, detailed evaluations across multiple dimensions,
    and an executive summary.
    """

    overall_rating: float = Field(
        ge=0.0, le=10.0, description="Overall performance rating from 0-10 (average of all evaluation scores)"
    )
    evaluations: PerformanceEvaluations = Field(description="Detailed evaluations for each performance dimension")
    summary: str = Field(description="Executive summary of the evaluation with key findings and recommendations")
