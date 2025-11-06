"""Role for evaluating agent conversation performance.

This role analyzes agent conversations to assess performance across multiple
dimensions and provide structured feedback with improvement suggestions.
"""

from pydantic_ai import Tool

from devboard.agents.evaluation_models import ConversationAnalysis
from devboard.agents.roles.base import Role

EVALUATOR_ROLE_PROMPT = """
You are a Conversation Evaluation Specialist for DevBoard, responsible for analyzing agent conversations and providing structured feedback to improve agent performance.

Your role is to evaluate agent conversations by assessing:
- **System Prompt Effectiveness**: How well the system prompt guides agent behavior, clarity of instructions, handling of edge cases, and completeness
- **Tool Specification Quality**: Quality of tool definitions including naming, descriptions, parameter clarity, and appropriateness of approval requirements
- **Context Management**: Effectiveness of initial context provided and how well the agent uses available context throughout the conversation
- **Response Quality**: Quality of agent responses including accuracy, relevance, helpfulness, and appropriateness
- **Conversation Efficiency**: How efficiently the agent achieves its goals, appropriate tool usage, minimal unnecessary steps, and clear reasoning

EVALUATION GUIDELINES:

1. **Be Objective and Evidence-Based**:
   - Base all scores and observations on concrete evidence from the conversation
   - Reference specific events, messages, or tool calls in your evidence lists
   - Use event IDs or message numbers as references (e.g., "tool_call_5", "message_3")

2. **Use the Full 0-10 Scale**:
   - 0-3: Poor performance with significant issues
   - 4-5: Below average with notable problems
   - 6-7: Acceptable performance with room for improvement
   - 8-9: Good performance with minor issues
   - 10: Excellent performance with no significant issues

3. **Provide Actionable Improvements**:
   - Each improvement should be specific and implementable
   - Include concrete suggested changes (e.g., exact prompt additions, tool modifications)
   - Explain the expected impact of implementing the change
   - Prioritize improvements based on potential impact (HIGH, MEDIUM, LOW)

4. **Consider Context and Role**:
   - Evaluate the agent based on its role type and intended purpose
   - Consider the complexity of the task and user requests
   - Account for the engine and model limitations
   - Recognize when external factors (unclear user input, missing context) affect performance

5. **Balance Positive and Constructive Feedback**:
   - Acknowledge what the agent does well in explanations
   - Provide constructive criticism for areas needing improvement
   - Focus on systemic issues rather than one-off mistakes
   - Look for patterns across multiple interactions

EVALUATION PROCESS:

1. **Review Agent Specification**:
   - Analyze the system prompt for clarity, completeness, and potential ambiguities
   - Examine tool definitions for appropriate naming, descriptions, and parameters
   - Assess initial context for relevance and completeness

2. **Analyze Conversation Flow**:
   - Follow the chronological sequence of events
   - Identify patterns in agent behavior and tool usage
   - Note any issues, confusion, or suboptimal decisions
   - Evaluate response quality and relevance

3. **Identify Improvement Opportunities**:
   - Look for areas where the system prompt could be clearer or more comprehensive
   - Identify missing tools or poorly specified existing tools
   - Find gaps in context or context management issues
   - Recognize opportunities to improve conversation efficiency

4. **Calculate Scores**:
   - Score each dimension independently based on observed performance
   - Calculate overall rating as the average of all dimension scores
   - Ensure scores reflect evidence from the conversation

5. **Write Summary**:
   - Provide a concise executive summary (2-3 paragraphs)
   - Highlight key strengths and most critical areas for improvement
   - Offer overall recommendations for enhancing agent performance

OUTPUT FORMAT:

You must respond with a structured JSON output matching the ConversationEvaluation schema:

{
  "overall_rating": <float 0-10, average of all dimension scores>,
  "evaluations": {
    "system_prompt_effectiveness": {
      "score": <float 0-10>,
      "explanation": "<detailed explanation of score>",
      "evidence": ["<reference_1>", "<reference_2>", ...],
      "improvements": [
        {
          "priority": "<high|medium|low>",
          "title": "<brief improvement title>",
          "description": "<detailed description of issue>",
          "suggested_changes": "<specific changes to make>",
          "expected_impact": "<expected improvement from change>"
        },
        ...
      ]
    },
    "tool_specification_quality": { ... },
    "context_management": { ... },
    "response_quality": { ... },
    "conversation_efficiency": { ... }
  },
  "summary": "<executive summary with key findings and recommendations>"
}

IMPORTANT NOTES:
- Provide evaluations for ALL five dimensions, even if some have no improvements
- Empty improvements list is acceptable if performance in that area is excellent
- Be thorough but concise in explanations (2-4 sentences per dimension)
- Focus on actionable, specific improvements rather than vague suggestions
- Maintain professional, constructive tone throughout the evaluation
"""


class ConversationEvaluatorRole(Role):
    """Role for evaluating agent conversation performance.

    This role analyzes a conversation and its agent configuration to provide
    structured feedback across multiple performance dimensions. The conversation
    to be evaluated is provided via the context, and the evaluator produces a
    structured ConversationEvaluation as output.
    """

    def __init__(self, conversation_analysis: ConversationAnalysis):
        """Initialize conversation evaluator role.

        Args:
            conversation_analysis: Complete conversation data to be evaluated
        """
        self.conversation_analysis = conversation_analysis

    def get_system_prompt(self) -> str:
        """Get the system prompt for conversation evaluator role.

        Returns:
            System prompt guiding the evaluation process
        """
        return EVALUATOR_ROLE_PROMPT

    def get_tools(self) -> list[Tool]:
        """Get tools for conversation evaluator role.

        The evaluator is a pure analysis role and does not require any tools.
        All necessary data is provided in the initial context.

        Returns:
            Empty list (no tools needed)
        """
        return []

    async def get_context_content(self) -> str:
        """Get context content for conversation evaluator role.

        Formats the conversation analysis into a comprehensive context string
        for the evaluator to analyze.

        Returns:
            Formatted context containing agent specification and conversation events
        """
        analysis = self.conversation_analysis
        spec = analysis.agent_specification

        # Format tool specifications
        tools_section = ""
        if spec.tools:
            tools_section = "\n\nAVAILABLE TOOLS:\n"
            for tool in spec.tools:
                tools_section += f"\n- **{tool.name}**"
                if tool.requires_approval:
                    tools_section += " (requires user approval)"
                tools_section += f"\n  Description: {tool.description}\n"
                if tool.parameters:
                    tools_section += f"  Parameters: {tool.parameters}\n"

        # Format builtin tools if any
        builtin_tools_section = ""
        if spec.allowed_builtin_tools:
            builtin_tools_section = f"\n\nALLOWED ENGINE BUILTIN TOOLS:\n{', '.join(spec.allowed_builtin_tools)}\n"

        # Format conversation events
        events_section = "\n\nCONVERSATION EVENTS (chronological order):\n\n"
        for idx, event in enumerate(analysis.events, 1):
            event_dict = event.model_dump()
            event_type = event_dict.get("event_type", "unknown")

            if event_type == "message":
                role = event_dict.get("role", "unknown")
                text = event_dict.get("text_content", "")
                events_section += f"{idx}. [{event_type}] {role.upper()}: {text[:200]}{'...' if len(text) > 200 else ''}\n"

            elif event_type == "tool_call_request":
                tool_name = event_dict.get("tool_name", "unknown")
                tool_args = event_dict.get("tool_args", {})
                events_section += f"{idx}. [{event_type}] Tool: {tool_name}\n"
                events_section += f"    Args: {str(tool_args)[:200]}{'...' if len(str(tool_args)) > 200 else ''}\n"

            elif event_type == "tool_call":
                tool_name = event_dict.get("tool_name", "unknown")
                tool_call_id = event_dict.get("tool_call_id", "unknown")
                events_section += f"{idx}. [{event_type}] Tool: {tool_name} (ID: {tool_call_id})\n"

            elif event_type == "tool_result":
                tool_call_id = event_dict.get("tool_call_id", "unknown")
                is_error = event_dict.get("is_error", False)
                result = event_dict.get("result_content", "")
                status = "ERROR" if is_error else "SUCCESS"
                events_section += f"{idx}. [{event_type}] {status} (ID: {tool_call_id})\n"
                events_section += f"    Result: {result[:200]}{'...' if len(result) > 200 else ''}\n"

        # Build complete context
        context = f"""
CONVERSATION TO EVALUATE:
========================

METADATA:
- Conversation ID: {analysis.conversation_id}
- Agent Role: {spec.role_type}
- Engine: {analysis.engine}
- Model: {analysis.model_id}
- Started At: {analysis.started_at}
- Total Events: {analysis.event_count}
- Tool Calls: {analysis.tool_call_count}

AGENT SPECIFICATION:
--------------------

SYSTEM PROMPT:
```
{spec.system_prompt}
```
{tools_section}{builtin_tools_section}

INITIAL CONTEXT PROVIDED TO AGENT:
```
{spec.context_summary}
```
{events_section}

========================
END OF CONVERSATION DATA
========================

Please evaluate this conversation across all five dimensions and provide your structured assessment.
"""

        return context.strip()
