# LLM Providers

**Navigation**: [Documentation Home](../INDEX.md) > [Integrations](./INDEX.md) > LLM Providers

**Purpose**: Multi-provider LLM support (OpenAI, Anthropic, Google) for flexible agent execution

## Providers

### OpenAI

**Models**: GPT-5, o-series (reasoning), GPT-4 Turbo/GPT-4o (fast)

**Auth**: `OPENAI_API_KEY`

**Capabilities**: Function calling, vision (GPT-4V), JSON mode, streaming

### Anthropic

**Models**: Sonnet 4.5, Opus 4.1 (reasoning), Haiku 3.7 (fast)

**Auth**: `ANTHROPIC_API_KEY`

**Capabilities**: Tool use, 200K+ context, vision, streaming

**Claude Code**: Direct CLI integration

### Google

**Models**: Gemini 2.5 Pro (reasoning), Gemini 2.5 Flash (fast)

**Auth**: `GOOGLE_API_KEY` or `GOOGLE_AI_STUDIO_API_KEY`

**Capabilities**: Function calling, multimodal, large context, code execution

## Architecture

**LLM Service** (`backend/devboard/agents/language_models.py`): Centralized provider management, model selection, fallback handling, retries

**Selection**:
1. Explicit configuration
2. Fallback to available provider
3. Error if none available

## Configuration

**Env Variables**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`

**Validation** (`backend/devboard/config/llm_providers.py`): Key presence checks, optional test calls, provider availability

## Model Registry

**Location**: `backend/devboard/agents/language_models.py`

**LanguageModel**: `id` ("provider:model"), `provider`, `name`, `type` (REASONING/FAST)

**Organization**: By provider and type

**Role Recommendations**:
- PROJECT, TASK_PLANNING → REASONING
- INVESTIGATION → FAST
- External engines (Claude Code, Gemini CLI) can use own defaults

## Model Selection

**Default** (role-based):
- Role determines type (REASONING/FAST)
- Engine filters provider
- Validate availability

**Explicit**: User configuration via UI, validated for engine compatibility

## PydanticAI Integration

**Framework**: PydanticAI for agent conversations and tool calling

**Provider Adapters**: Handle provider-specific APIs

**Streaming**: Real-time responses for all providers

**Tool Calling**: Unified interface across providers

## Rate Limiting

**OpenAI**: Tier-based RPM/TPM, exponential backoff

**Anthropic**: Request-based, auto-detection, graceful degradation

**Google**: Quota-based, daily limits, throttling

**Error Handling**: Detect rate limits, auto-retry, user notification

## Model Availability

**Service**: `backend/devboard/agents/agent_config_service.py`

**Checking**:
- Configured providers (valid API keys)
- Filter catalog for INTERNAL engine
- External engines show all provider models (no API key filter)

**API**: `GET /api/agents/available-models` - Models grouped by engine

## Cost Management

**Model Types**:
- **Reasoning** (higher cost): GPT-5, o-series, Opus, Sonnet, Gemini Pro
- **Fast** (lower cost): GPT-4 Turbo, Haiku, Gemini Flash

**Optimization**: Role-appropriate models, fallback strategy, usage monitoring (future)

## Files

**LLM Service**: `backend/devboard/agents/language_models.py`

**Config**: `backend/devboard/config/llm_providers.py`, `backend/devboard/services/config_service.py`, `backend/devboard/agents/agent_config_service.py`

**API**: `backend/devboard/api/routers/agents.py`

## See Also

[Agent Configuration](../4-ai-agents/configuration.md) | [Agent Architecture](../4-ai-agents/agent-architecture.md)
