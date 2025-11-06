# AI Conversation Evaluator

## Overview

The AI Conversation Evaluator is a new agent role and service that analyzes agent conversations to assess performance and suggest improvements to system prompts, tool specifications, and context management.

## Architecture

### Components

1. **Data Models** (`devboard/agents/evaluation_models.py`)
   - `AgentSpecification` - Formatted representation of agent configuration
   - `ConversationAnalysis` - Complete conversation data for evaluation
   - `ConversationEvaluation` - Structured evaluation result
   - `PerformanceEvaluations` - Detailed metrics across 5 dimensions
   - `Evaluation` - Individual dimension assessment with score, explanation, evidence, and improvements
   - `Improvement` - Specific actionable suggestion
   - `Priority` - HIGH/MEDIUM/LOW priority levels
   - `ToolSpecification` - Tool definition for evaluation

2. **Evaluator Role** (`devboard/agents/roles/conversation_evaluator.py`)
   - `ConversationEvaluatorRole` - Agent role that performs the evaluation
   - Uses INTERNAL engine only (PydanticAI with structured output)
   - No tools required (pure analysis)
   - Comprehensive system prompt guiding the evaluation process

3. **Evaluation Service** (`devboard/services/conversation_evaluator_service.py`)
   - `ConversationEvaluatorService` - Business logic for evaluation
   - Retrieves conversation and messages from database
   - Reconstructs agent specification from Role class
   - Converts messages to events
   - Executes evaluator agent with structured output
   - Returns `ConversationEvaluation` result

4. **Tests** (`backend/tests/test_conversation_evaluator.py`)
   - Unit tests for service methods
   - Integration tests for evaluation flow
   - Model validation tests

## Evaluation Dimensions

The evaluator assesses agent performance across five dimensions:

1. **System Prompt Effectiveness** (0-10)
   - Clarity and completeness of instructions
   - Handling of edge cases
   - Absence of conflicting instructions
   - Alignment with role purpose

2. **Tool Specification Quality** (0-10)
   - Tool naming appropriateness
   - Description clarity
   - Parameter specification completeness
   - Approval requirement correctness

3. **Context Management** (0-10)
   - Sufficiency of initial context
   - Relevance of provided information
   - Context usage throughout conversation
   - Identification of missing resources

4. **Response Quality** (0-10)
   - Accuracy of agent responses
   - Relevance to user queries
   - Helpfulness and clarity
   - Appropriateness of actions

5. **Conversation Efficiency** (0-10)
   - Optimal tool usage
   - Minimal unnecessary steps
   - Clear reasoning and decision-making
   - Goal achievement effectiveness

## Data Flow

```
1. Input: conversation_id + optional evaluator_model_id
   ↓
2. Service retrieves conversation and messages from database
   ↓
3. Service reconstructs agent Role instance
   ↓
4. Service extracts:
   - System prompt from role
   - Tools from role
   - Initial context from role
   - Conversation events from messages
   ↓
5. Service creates ConversationAnalysis object
   ↓
6. Service creates ConversationEvaluatorRole with analysis
   ↓
7. Service creates PydanticAI agent with structured output type
   ↓
8. Agent analyzes and returns ConversationEvaluation
   ↓
9. Output: Structured evaluation with scores and improvements
```

## Usage

### Programmatic Usage

```python
from devboard.services.conversation_evaluator_service import ConversationEvaluatorService

# Initialize service (usually via dependency injection)
evaluator_service = ConversationEvaluatorService(
    conversation_repo=conversation_repo,
    project_repo=project_repo,
    task_repo=task_repo,
    document_repo=document_repo,
)

# Evaluate a conversation
evaluation = await evaluator_service.evaluate_conversation(
    conversation_id=123,
    evaluator_model_id="anthropic:claude-sonnet-4"  # Optional
)

# Access results
print(f"Overall Rating: {evaluation.overall_rating}/10")
print(f"System Prompt Score: {evaluation.evaluations.system_prompt_effectiveness.score}/10")

# Access improvements
for improvement in evaluation.evaluations.system_prompt_effectiveness.improvements:
    print(f"[{improvement.priority}] {improvement.title}")
    print(f"  Suggestion: {improvement.suggested_changes}")
    print(f"  Impact: {improvement.expected_impact}")
```

### Example Output Structure

```json
{
  "overall_rating": 8.2,
  "evaluations": {
    "system_prompt_effectiveness": {
      "score": 8.5,
      "explanation": "System prompt is clear and comprehensive with good behavioral guidelines. Minor improvements needed for edge case handling.",
      "evidence": ["message_1", "tool_call_3"],
      "improvements": [
        {
          "priority": "medium",
          "title": "Add guidance for handling ambiguous user input",
          "description": "The agent showed hesitation when user provided vague requirements in message 5. Clear guidance on asking clarifying questions would help.",
          "suggested_changes": "Add section: 'When requirements are unclear or ambiguous, ask 2-3 specific clarifying questions before proceeding.'",
          "expected_impact": "Reduce unnecessary tool calls and improve first-time accuracy by 20%"
        }
      ]
    },
    "tool_specification_quality": {
      "score": 9.0,
      "explanation": "Tools are well-named with clear descriptions and appropriate parameters.",
      "evidence": ["tool_spec_1", "tool_spec_2"],
      "improvements": []
    },
    "context_management": {
      "score": 7.5,
      "explanation": "Initial context is relevant but could be more comprehensive. Agent managed context well during conversation.",
      "evidence": ["context_1", "message_7"],
      "improvements": [
        {
          "priority": "high",
          "title": "Include recent project activity in context",
          "description": "Agent had to ask about recent changes that could have been in initial context.",
          "suggested_changes": "Add last 5 commits and recent PR activity to initial context",
          "expected_impact": "Reduce context-gathering tool calls by 30%"
        }
      ]
    },
    "response_quality": {
      "score": 8.0,
      "explanation": "Responses are generally accurate and helpful with good explanations.",
      "evidence": ["message_2", "message_6"],
      "improvements": []
    },
    "conversation_efficiency": {
      "score": 8.0,
      "explanation": "Good conversation flow with appropriate tool usage. One unnecessary tool call at message 8.",
      "evidence": ["tool_call_8"],
      "improvements": [
        {
          "priority": "low",
          "title": "Optimize information gathering",
          "description": "Agent made redundant search at message 8 for information available in context.",
          "suggested_changes": "Update prompt to emphasize checking context before tool calls",
          "expected_impact": "Minor efficiency improvement of ~5%"
        }
      ]
    }
  },
  "summary": "Overall strong performance with clear room for improvement in context management. System prompt is effective but could benefit from more specific guidance on handling ambiguous input. Tool specifications are excellent. Response quality is high with accurate and helpful information. Conversation flow is generally efficient with minor optimization opportunities."
}
```

## Implementation Details

### Agent Role Configuration

- **Role Type**: `AgentRoleType.CONVERSATION_EVALUATOR`
- **Allowed Engines**: `[AgentEngine.INTERNAL]` only
- **Tools**: None (pure analysis role)
- **Output Type**: `ConversationEvaluation` (structured Pydantic model)

### Evaluation Process

1. **Conversation Retrieval**
   - Fetches conversation metadata and all messages from database
   - Validates conversation exists and has messages

2. **Role Reconstruction**
   - Creates appropriate Role instance (ProjectQARole, TaskSpecificationRole, etc.)
   - Extracts system prompt, tools, and context from role

3. **Agent Specification Formatting**
   - Converts PydanticAI Tools to `ToolSpecification` objects
   - Extracts parameter schemas from tool definitions
   - Truncates context to first 5000 chars for summary

4. **Message Conversion**
   - Converts `ConversationMessage` objects to `ConversationEvent` objects
   - Parses PydanticAI messages to extract tool calls and results
   - Maintains chronological order with timestamps

5. **Evaluation Execution**
   - Creates `ConversationEvaluatorRole` with formatted analysis
   - Creates PydanticAI agent with `ConversationEvaluation` output type
   - Runs agent with single prompt: "Please evaluate this conversation."
   - All analysis data provided in initial context

6. **Result Parsing**
   - PydanticAI ensures structured output matching schema
   - Validates all required fields are present
   - Returns typed `ConversationEvaluation` object

### Model Selection

The evaluator defaults to `anthropic:claude-sonnet-4` if available, otherwise uses the first configured model. A different model can be specified via the `evaluator_model_id` parameter.

### Evidence References

Evidence lists contain references to specific conversation elements:
- `message_N` - Refers to the Nth message in conversation
- `tool_call_N` - Refers to a specific tool call
- `tool_spec_N` - Refers to a tool specification
- `context_1` - Refers to initial context

These can be used to cross-reference specific parts of the conversation.

## Testing

The implementation includes comprehensive tests:

- **Unit Tests**: Test individual service methods
  - Message to event conversion
  - Tool parameter extraction
  - Agent specification formatting
  - Error handling for missing conversations/messages

- **Integration Tests**: Test full evaluation flow
  - End-to-end evaluation with mocked agent output
  - Proper handling of different conversation types
  - Validation of output structure

- **Model Tests**: Test Pydantic model validation
  - Evaluation model creation
  - Nested improvement structures
  - Priority enum handling

Run tests with: `make test` (from `backend/` directory)

## Future Enhancements

Potential improvements for the evaluator:

1. **Batch Evaluation**
   - Analyze multiple conversations to find patterns
   - Compare performance across different agent configurations
   - Identify systematic issues

2. **Trend Analysis**
   - Track evaluation scores over time
   - Identify improvements or regressions
   - Measure impact of prompt changes

3. **Automated Improvements**
   - Auto-generate prompt modifications based on suggestions
   - A/B test different configurations
   - Learn from successful conversations

4. **Custom Criteria**
   - Allow user-defined evaluation dimensions
   - Domain-specific metrics (e.g., code quality, customer service)
   - Weighted scoring based on priorities

5. **Comparative Analysis**
   - Compare different agent roles
   - Benchmark against baseline performance
   - Identify best practices

6. **Evaluation Persistence**
   - Store evaluation results in database
   - Track evaluation history for conversations
   - Enable querying and filtering of evaluations

7. **Frontend Integration**
   - UI for viewing evaluation results
   - Visual representation of scores
   - Interactive improvement suggestions
   - One-click prompt updates

## Files Modified/Created

### Created
- `backend/devboard/agents/evaluation_models.py` - Pydantic models for evaluation
- `backend/devboard/agents/roles/conversation_evaluator.py` - Evaluator agent role
- `backend/devboard/services/conversation_evaluator_service.py` - Evaluation service
- `backend/tests/test_conversation_evaluator.py` - Test suite
- `CONVERSATION_EVALUATOR.md` - This documentation

### Modified
- `backend/devboard/agents/roles/types.py` - Added `CONVERSATION_EVALUATOR` to enum
- `backend/devboard/agents/engines/agent_engines.py` - Added evaluator to compatibility matrix

## Configuration

No additional configuration is required. The evaluator uses:
- Existing LLM registry for model selection
- Existing role system for agent specification extraction
- Existing conversation/message repositories for data access

## Dependencies

The evaluator leverages existing dependencies:
- PydanticAI - For structured output and agent execution
- SQLAlchemy - For database access via repositories
- Pydantic - For data validation and serialization

No new dependencies added.

## Integration Points

The evaluator integrates seamlessly with existing architecture:

1. **Role System**: New role follows `Role` interface
2. **Agent Framework**: Uses `InternalAgent` with PydanticAI
3. **Conversation API**: Leverages existing conversation retrieval
4. **Event System**: Reuses `ConversationEvent` types
5. **LLM Registry**: Uses configured models

## Security Considerations

- Evaluator only reads conversation data (no modifications)
- No external API calls (beyond configured LLM provider)
- Follows existing authentication/authorization patterns
- Evaluation data contains potentially sensitive conversation content

## Performance

- Evaluation time: ~10-30 seconds for typical conversation (depends on model)
- Handles conversations with 100+ events efficiently
- Context truncation for very large contexts (>5000 chars)
- Stateless evaluation enables parallel execution

## Conclusion

The AI Conversation Evaluator provides a powerful tool for assessing and improving agent performance. By providing structured, evidence-based feedback across multiple dimensions, it enables iterative refinement of agent configurations to achieve better results over time.
