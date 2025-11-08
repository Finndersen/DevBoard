# Agent Architecture

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Agent Architecture

## Overview

DevBoard's AI agent system implements a sophisticated role-based architecture that separates agent behavior from execution engines. This design enables the same agent role to run on different execution platforms (Internal PydanticAI, Claude Code CLI, Gemini CLI) while maintaining consistent behavior and tool capabilities.

## Core Architecture Principles

**Separation of Concerns**: Agent behavior (defined by Roles) is completely independent of execution mechanism (defined by Engines).

**Unified Interface**: All agents implement the same BaseAgent interface, providing consistent API regardless of execution engine.

**Tool Portability**: Tools are defined once in engine-agnostic format and automatically converted for each engine's native format.

**Event-Based Communication**: Agents return structured event streams rather than single responses, providing complete visibility into operations.

## BaseAgent Interface

The foundation of the agent system is the abstract BaseAgent class that all agent implementations must implement.

**Location**: `backend/devboard/agents/base_agent.py`

**Core Methods**:
- **`run(prompt_or_approvals)`**: Execute agent synchronously, returns complete `list[ConversationEvent]`
- **`stream_events(prompt_or_approvals)`**: Stream events asynchronously as they're generated via `AsyncIterator[ConversationEvent]`

**Parameters**: Accept either a user message string or tool approval results (`str | ToolApprovals`)

**Return Types**: Generate ConversationEvent objects (ConversationMessage, ToolCallRequest, ToolCall, ToolResult)

**Event Parsing**: Each agent implementation converts its native format to ConversationEvents internally

**Timestamp Generation**: Events include timestamps generated during parsing for chronological ordering

## Agent Engines

DevBoard supports multiple agent execution engines, each with different capabilities and characteristics.

### Engine Implementations

**InternalAgent** (`INTERNAL` engine):
- Native PydanticAI agent with built-in tool execution
- Tools execute automatically with validation
- Generates ToolCall and ToolResult events for completed executions
- Requires explicit model selection
- Location: `backend/devboard/agents/engines/internal/agent.py`

**ClaudeCodeAgent** (`CLAUDE_CODE` engine):
- Integration with Claude Code CLI via `claude-agent-sdk`
- Converts Role tools to "virtual tools" requiring user approval
- Generates ToolCallRequest events for approval workflow
- Supports session resumption and full Claude Code capabilities
- Can use engine's default model or explicit selection
- Location: `backend/devboard/agents/engines/claude_code/agent.py`

**Future Engines**:
- Gemini CLI integration planned
- Other execution engines can be added following BaseAgent interface

### Engine Selection

Engines are selected based on:
- **Agent Role Requirements**: Some roles require specific engines (e.g., PROJECT role requires INTERNAL for tool approval)
- **User Configuration**: Users can configure preferred engines for each role
- **Model Availability**: Engine must support configured LLM provider

## Role-Based Architecture

Roles define agent behavior independently of the execution engine, encapsulating system prompts, tools, and context assembly logic.

### Role Abstract Class

**Location**: `backend/devboard/agents/roles/base.py`

**Core Methods**:
- **`get_system_prompt()`**: Returns complete system prompt with role description and instructions
- **`get_tools()`**: Returns tool definitions in engine-agnostic PydanticAI `Tool` format
- **`get_context_content()`**: Returns formatted context string (entity state, documents, etc.)

**Engine Agnostic**: Same role can run on Internal or Claude Code engines

**Tool Conversion**: Each engine converts PydanticAI tools to its native format automatically

### Implemented Roles

**ProjectQARole**:
- Purpose: Answer project questions and edit project specifications
- Context: Project details, specifications, linked resources
- Tools: `edit_project_specification`, `search_codebase`, `read_codebase_files`
- Engine Support: INTERNAL or CLAUDE_CODE
- Location: `backend/devboard/agents/roles/project_qa.py`

**TaskSpecificationRole**:
- Purpose: Guide task requirement gathering during SPECIFICATION phase
- Context: Task details, specification document, project context
- Tools: `edit_task_specification`, `set_task_specification_content`, `search_codebase`, `read_codebase_files`
- Engine Support: INTERNAL or CLAUDE_CODE
- Location: `backend/devboard/agents/roles/task_specification.py`

**TaskPlanningRole**:
- Purpose: Create implementation plans during PLANNING phase
- Context: Task specification, implementation plan document
- Tools: `edit_implementation_plan`, `set_implementation_plan_content`, `search_codebase`, `read_codebase_files`, `execute_shell_command`
- Engine Support: INTERNAL or CLAUDE_CODE
- Location: `backend/devboard/agents/roles/task_planning.py`

**TaskImplementationRole**:
- Purpose: Assist with code implementation during IMPLEMENTATION phase
- Context: Task specification, implementation plan, codebase structure
- Tools: `search_codebase`, `read_codebase_files`, `execute_shell_command`
- Engine Support: INTERNAL or CLAUDE_CODE
- Location: `backend/devboard/agents/roles/task_implementation.py`

**CodebaseInvestigationRole**:
- Purpose: Investigate codebases to answer implementation questions and provide analysis
- Context: Codebase information, directory tree, documentation index
- Tools: `search_file_content`, `search_files_by_name`, `search_code_structure`, `show_directory_tree`, `read_file`
- Engine Support: INTERNAL or CLAUDE_CODE
- Location: `backend/devboard/agents/roles/codebase_investigation.py`
- Note: Used as a sub-agent by other roles via `investigate_codebase` tool

**DocumentationMaintainerRole**:
- Purpose: Create and maintain codebase documentation following documentation standards
- Context: Codebase information, directory tree, documentation index, maintenance guide
- Tools: `investigate_codebase`, `search_file_content`, `search_files_by_name`, `search_code_structure`, `show_directory_tree`, `read_file`
- Engine Support: INTERNAL or CLAUDE_CODE
- Location: `backend/devboard/agents/roles/documentation_maintainer.py`

### Dynamic Role Selection

The system automatically selects the appropriate role based on entity type and state.

**Location**: Agent role selection logic is implemented in the agent configuration service

**Selection Logic**:
- Project Conversations: Always use ProjectQARole
- Task Conversations: Select based on task.state
  - DEFINING/DESIGNING → TaskSpecificationRole
  - PLANNING → TaskPlanningRole
  - IMPLEMENTING/IN_REVIEW/COMPLETE → TaskImplementationRole
- Codebase Conversations: Reserved for future investigation agent roles

## Tool System

Tools are defined once in PydanticAI format within Role classes and automatically converted for each engine.

**Definition Location**: `backend/devboard/agents/tools.py`

**Format**: Uses PydanticAI `Tool` class with function, docstrings, and `requires_approval` flag

**Engine Conversion**:
- **InternalAgent**: Uses PydanticAI tools directly with built-in validation
- **ClaudeCodeAgent**: Converts to VirtualTools (if `requires_approval=True`) or function tools

## Agent Construction

Agents are initialized with a Role and optional model configuration:

```python
agent = ClaudeCodeAgent(
    role=TaskPlanningRole(task),  # Role defines behavior
    model=language_model,          # Optional (None uses engine default)
    session_id=session_id          # For Claude Code continuity
)
```

**Role Parameter**: Defines agent behavior, tools, and prompts

**Model Parameter**: Optional language model configuration (None uses engine default)

**Session Parameter**: For Claude Code, enables conversation continuity

## Event-Based Response Architecture

Agents return event streams rather than single responses, providing complete conversation timeline.

**Event Types**:
- ConversationMessage: Text messages from user or agent
- ToolCall: Agent's request to execute a tool (InternalAgent)
- ToolResult: Execution result from completed tool call (InternalAgent)
- ToolCallRequest: Virtual tool call requiring approval (ClaudeCodeAgent)

**Event Parsing**: Each agent implementation converts its native format to ConversationEvents internally

**Streaming Support**: Both synchronous (`run()`) and streaming (`stream_events()`) execution modes

## Implementation Reference

**Core Agent Files**:
- `backend/devboard/agents/base_agent.py`: Abstract base class
- `backend/devboard/agents/base_agent_conversation.py`: Conversation service base
- `backend/devboard/agents/agent_config_service.py`: Agent configuration and engine selection
- `backend/devboard/agents/events.py`: Event type definitions
- `backend/devboard/agents/language_models.py`: Multi-provider LLM management
- `backend/devboard/agents/tools.py`: Tool definitions
- `backend/devboard/agents/prompt_actions.py`: Prompt action handling

**Agent Engines**:
- `backend/devboard/agents/engines/agent_engines.py`: Engine registry
- `backend/devboard/agents/engines/internal/`: PydanticAI implementation (agent.py, agent_conversation.py, deps.py, utils.py)
- `backend/devboard/agents/engines/claude_code/`: Claude Code implementation (agent.py, agent_conversation.py, client.py, message_parser.py, session.py, tool_approval_manager.py, virtual_tools.py)
- `backend/devboard/agents/engines/gemini_cli.py`: Gemini CLI integration

**Agent Roles**:
- `backend/devboard/agents/roles/base.py`: Role abstract class
- `backend/devboard/agents/roles/project_qa.py`: Project Q&A role
- `backend/devboard/agents/roles/task_specification.py`: Task specification role
- `backend/devboard/agents/roles/task_planning.py`: Task planning role
- `backend/devboard/agents/roles/task_implementation.py`: Task implementation role
- `backend/devboard/agents/roles/codebase_investigation.py`: Codebase investigation role
- `backend/devboard/agents/roles/documentation_maintainer.py`: Documentation maintainer role
- `backend/devboard/agents/roles/types.py`: Role type definitions
