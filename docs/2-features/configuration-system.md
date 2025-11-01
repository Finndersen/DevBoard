# Configuration System

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > Configuration System

**Purpose**: Unified settings interface for integrations, agents, codebases, env vars with multi-source precedence

## Configuration Areas

### Integration Management

**Services**: GitHub (repos, API, rate limits), Jira (projects, tickets, auth), Slack (channels, bots, conversations), AI Providers (OpenAI/Anthropic/Google keys)

**Features**: Configure credentials, test connections, view status, enable/disable independently

### Codebase Management

**Operations**: Add (register new), validate paths (verify existence), edit metadata (name, description, paths), remove (data only, not code)

### Agent Configuration

**Roles**: PROJECT (Q&A, spec editing), TASK_SPECIFICATION (requirements), TASK_PLANNING (plans), TASK_IMPLEMENTATION (code), INVESTIGATION (analysis)

**Engines**: INTERNAL (PydanticAI, tool approval), CLAUDE_CODE (Anthropic CLI), GEMINI_CLI (Google CLI)

**Model Selection**:
- Provider-filtered (Claude Code → Anthropic only, Gemini CLI → Google only, Internal → all configured)
- Engine requirements (some require explicit, others support default)
- Default option (external engines can use engine default)
- Required for INTERNAL (explicit model choice)

**Defaults**: REASONING models (planning), FAST models (quick tasks), role-based restrictions (PROJECT requires INTERNAL for approval)

### Resource Management

**Operations**: Add external resources (GitHub repos, Jira tickets, Slack threads, web pages), URI-based linking, resource descriptions, shared resources (same resource across entities)

### Environment Integration

**Features**: Display env vars, UI override capability, source indication (env/UI/default), real-time validation

## Behavior

**Multi-Source Precedence**:
1. Environment variables (highest)
2. UI-configured settings (database)
3. Default values (application defaults)

**Source transparency** in UI

**Real-Time Validation**: Test button per integration, immediate feedback, validation errors with guidance, partial configuration OK

**Clear Sources**: Env/UI/Default badges, override capability

**Graceful Degradation**: Optional integrations (GitHub/Jira/Slack), required (AI providers for agents), partial functionality, clear active/inactive indicators

## Settings Organization

**Integrations Tab**: GitHub/Jira/Slack config + testing, connection status

**AI Providers Tab**: OpenAI/Anthropic/Google keys, model availability, defaults

**Agent Configuration Tab**: Role-by-role engine selection, model selection per role, current config, default indicators

**Codebases Tab**: List, add/edit/delete, path validation

**Environment Tab**: Var display, source indication, override capability, validation status

## Use Cases

**Initial Setup**: Settings → Configure AI keys → Optional integrations → Register codebases → Configure agents → Test connections

**Add Integration**: Settings → Integrations → Select type → Enter credentials → Test → Available for providers

**Configure Agent**: Settings → Agent Config → Select role → Choose engine → Select model (or default) → Immediate effect

**Register Codebase**: Settings → Codebases → Add → Enter name/description/path → Validate → Optional remote → Available for projects/tasks

**Override Env**: Identify env setting → UI override → UI takes precedence → Source shows "UI Override"
