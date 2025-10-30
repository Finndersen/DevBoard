# Agent Configuration

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Configuration

## Core Architecture

**Roles**: PROJECT, TASK_SPECIFICATION, TASK_PLANNING, TASK_IMPLEMENTATION, INVESTIGATION

**Engines**: INTERNAL (PydanticAI), CLAUDE_CODE, GEMINI_CLI

**Key Decision**: Roles restrict engines - e.g., PROJECT requires INTERNAL for tool approval

## Type System

**Location**: `backend/devboard/agents/types.py`

**Core Enums**: LLMProvider, ModelType, AgentEngine, AgentRole

**AgentEngineModelConfig**: `engine` + `model_id` (None = engine default)

**AgentConfiguration**: Response with current config + available options

**ModelInfo**: `id`, `provider`, `name`, `model_type`

## Engine Repository

**Location**: `backend/devboard/agents/agent_engines.py`

**AgentEngineDefinition**: `engine`, `display_name`, `description`, `available_provider`, `requires_model_selection`

**Engine Specs**:
- INTERNAL: All providers, requires model selection, tool approval
- CLAUDE_CODE: Anthropic only, optional model (CLI default)
- GEMINI_CLI: Google only, optional model (CLI default)

**Role Restrictions** (ALLOWED_ENGINES_BY_AGENT_ROLE):
- PROJECT → INTERNAL only
- TASK_SPECIFICATION → INTERNAL, CLAUDE_CODE
- TASK_PLANNING → INTERNAL, CLAUDE_CODE
- TASK_IMPLEMENTATION → CLAUDE_CODE, GEMINI_CLI
- INVESTIGATION → INTERNAL only

**Methods**: `get_engine_definition`, `get_available_engines_for_agent_role`, `get_default_engine_for_agent_role`, `validate_engine_for_agent_role`

## Model Repository

**Location**: `backend/devboard/agents/language_models.py`

**LanguageModel**: `id` ("provider:model"), `provider`, `name`, `type` (REASONING/FAST)

**Catalog**: Anthropic (Sonnet 4.5, Opus 4.1, Haiku 3.7), OpenAI (GPT-5, o-series, GPT-4), Google (Gemini 2.5 Pro/Flash)

**Role Recommendations** (RECOMMENDED_MODEL_TYPE_BY_AGENT_ROLE):
- PROJECT, TASK_PLANNING → REASONING
- INVESTIGATION → FAST

**Methods**: `get_all_models`, `get_models_for_provider`, `get_model_by_id`, `get_recommended_model_type_for_agent`

## Config Service

**Location**: `backend/devboard/agents/agent_config_service.py`

**Resolution Hierarchy** (get_effective_config):
1. Database config
2. Default engine for role
3. Default model for role+engine

**Validation** (update_agent_configuration):
1. Engine allowed for role
2. Model requirements (None only if `requires_model_selection=false`)
3. Model availability for engine
4. Prevents None model_id for INTERNAL

**Key Decision - Model Filtering** (_get_available_models_for_engine):
- INTERNAL: Filter by configured API keys
- External engines: Show all provider models (no API key check)
- Rationale: External CLIs manage their own credentials

**Default Selection** (_get_default_model_for_agent_role_and_engine):
1. Return None if engine supports default
2. Match recommended type for role
3. Fallback to first available

## System Integration

**Config Hierarchy** (`backend/devboard/services/config_service.py`):
1. Environment variables (highest)
2. Database (ConfigService)
3. Code defaults

**Database** (`backend/devboard/db/models/configuration.py`):
- Key-based JSON storage (e.g., "agent.project.default")
- AgentConfig schema: `selected_engine`, `selected_model`

**API** (`backend/devboard/api/routers/agents.py`):
- GET `/api/agents/{role}/configuration` - Full config + options
- PUT `/api/agents/{role}/configuration` - Update with validation
- GET `/api/agents/available-models` - Models by engine

**Frontend** (`frontend/src/components/configuration/AgentConfigurationSelector.tsx`):
1. Select role → Fetch engines
2. Select engine → Fetch models
3. Select model or "Default"
4. Save with validation

## Files

**Core**: `backend/devboard/agents/{types.py, agent_engines.py, language_models.py, agent_config_service.py}`

**Database**: `backend/devboard/db/models/configuration.py`, `backend/devboard/config/agent_config.py`

**API**: `backend/devboard/api/routers/agents.py`

**Frontend**: `frontend/src/components/configuration/AgentConfigurationSelector.tsx`

## See Also

[Agent Architecture](./agent-architecture.md) | [Claude Code Integration](./claude-code-integration.md) | [LLM Providers](../5-integrations/llm-providers.md)
