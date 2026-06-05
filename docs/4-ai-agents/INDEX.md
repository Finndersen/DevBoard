# AI Agents

**Navigation**: [Documentation Home](../INDEX.md) > AI Agents

## Purpose

This section provides comprehensive documentation of DevBoard's AI agent system. Learn about the role-based agent architecture, conversation patterns, tool capabilities, Claude Code integration, context assembly, and configuration.

## Overview

DevBoard employs a **role-based agent architecture** where agent behavior is determined by **Roles** (system prompts, tools, context), while **Agent Engines** (Internal, Claude Code, Gemini CLI) handle execution. This separation enables the same role to run on different engines with automatic tool conversion.

The **default engine is Claude Code SDK**, which uses your existing Claude Code / Claude.ai Pro subscription.

### Core Philosophy

- **Role-Based Design**: Agent behavior defined by interchangeable roles
- **Engine Agnostic**: Same role runs on Internal, Claude Code, or Gemini CLI engines
- **Event-Driven**: Agents return structured event streams for complete visibility
- **Tool-Based Interaction**: Agents request approval for document edits and operations
- **Context-Aware**: Agents understand full project/task context from multiple sources

## Documents

### [Agent Architecture](./agent-architecture.md)
BaseAgent interface, agent engines (Internal, Claude Code, Gemini CLI), agent roles, and role-based design philosophy.

### [Background Agents](./background-agents.md)
User-defined autonomous agents with manual, scheduled (cron), and event-based triggers; persistent state; run history.

### [Conversation System](./conversation-system.md)
Event-based conversations, ConversationEvent types (messages, tool calls, tool results, tool requests), streaming architecture, message persistence, and conversation repository.

### [Tools and Capabilities](./tools-and-capabilities.md)
Tool system implementation, available tools (document editing, codebase search, shell commands), approval workflows, and virtual tool calling pattern.

### [Claude Code Integration](./claude-code-integration.md)
Claude Code agent implementation, SDK vs interactive mode (billing), virtual tool calling architecture, session service, message parsing, validation and retry mechanisms, and sandbox configuration.

### [Context Assembly](./context-assembly.md)
Multi-source context gathering, context assembly service, strategy-based loading (eager vs on-demand), URI-based resource system, and integration with context providers.

### [Configuration](./configuration.md)
Agent engine configuration, model selection, role-based restrictions, intelligent defaults, multi-source configuration system, and agent configuration service.

## Agent Roles

DevBoard includes the following agent roles:

- **ProjectQARole**: Answer project questions and edit project specifications
- **TaskSpecificationRole**: Guide task requirement gathering and specification writing
- **TaskPlanningRole**: Create implementation plans and technical strategies
- **TaskImplementationRole**: Assist with code implementation and testing
- **InvestigationRole**: Codebase investigation and research
- **CodeReviewRole**: Review code changes and PRs
- **StepExecutionRole**: Execute individual steps of a structured implementation plan
- **BackgroundAgentRole**: Autonomous background agent execution

## Related Sections

- **[Features - Task Management](../2-features/task-management.md)**: How agents support task workflows
- **[Architecture - Backend Components](../3-architecture/backend/components.md)**: Agent implementation details
- **[Integrations - Context Providers](../5-integrations/context-providers.md)**: External context sources
- **[Features - Configuration System](../2-features/configuration-system.md)**: Agent configuration UI
