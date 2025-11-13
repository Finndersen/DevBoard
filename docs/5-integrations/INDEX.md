# Integrations

**Navigation**: [Documentation Home](../INDEX.md) > Integrations

## Purpose

This section describes how DevBoard connects to external services and systems. Learn about integration philosophy, external service connectors, context provider architecture, and LLM provider support.

## Overview

DevBoard integrates with your development ecosystem to provide AI agents with comprehensive context. The integration system is designed for:

- **Graceful Degradation**: System remains functional when integrations are unavailable
- **Multi-Source Context**: Combine data from multiple external sources
- **URI-Based Linking**: Simple URL references to external resources
- **Smart Loading**: Automatic determination of eager vs on-demand loading strategies
- **Error Resilience**: Continue functioning when individual integrations fail

## Documents

### [External Services](./external-services.md)
GitHub, Jira, and Slack integrations including authentication, API communication, data normalization, and rate limiting.

**Location**: `backend/devboard/integrations/`

### [Context Providers](./context-providers.md)
Context provider architecture, provider types (GitHub, Jira, Slack, Codebase, Webpage), URI-based resource system, and loading strategies.

**Location**: `backend/devboard/context_providers/`

### [LLM Providers](./llm-providers.md)
Multi-provider LLM support including OpenAI, Anthropic, and Google integrations. Model selection, fallback strategies, and provider configuration.

**Location**: `backend/devboard/agents/llm_service.py`

### [MCP Server](./mcp-server.md)
Model Context Protocol (MCP) server integration allowing DevBoard to act as a tool and resource provider for external AI clients. HTTP/SSE transport, tool scaffolding, and resource definitions.

**Location**: `backend/devboard/mcp/`

## Integration Types

### External Development Tools
- **GitHub**: Repository analysis, PR reviews, issue tracking, commit history
- **Jira**: Project management, ticket workflows, progress tracking
- **Slack**: Team communications, discussion threads, decision history

### AI & LLM Services
- **OpenAI**: GPT-4 and GPT-3.5 models
- **Anthropic**: Claude 3 family (Opus, Sonnet, Haiku)
- **Google**: Gemini models
- **MCP Server**: Model Context Protocol server for external AI clients

### Local Resources
- **Codebases**: File system analysis, architecture documentation
- **Web Resources**: Documentation sites, technical references

## Related Sections

- **[Features - Configuration System](../2-features/configuration-system.md)**: Integration configuration UI
- **[AI Agents - Context Assembly](../4-ai-agents/context-assembly.md)**: How context is gathered and assembled
- **[AI Agents - Configuration](../4-ai-agents/configuration.md)**: LLM provider configuration
- **[Architecture - Backend Components](../3-architecture/backend/components.md)**: Integration implementation
