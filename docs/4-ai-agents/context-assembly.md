# Context Assembly

**Navigation**: [Documentation Home](../INDEX.md) > [AI Agents](./INDEX.md) > Context Assembly

**Purpose**: Orchestrate multi-source context gathering with strategy-based loading for agents

**Location**: `backend/devboard/services/context_assembly.py`

## Architecture

**Multi-Source**: GitHub, Jira, Slack, codebases via pluggable providers

**Strategy-Based**: EAGER (load immediately) vs ON_DEMAND (list as available)

**URI-Based**: Standardized resource identification across providers

**Caching**: In-memory with TTL (default 5 min) for performance

## Provider Interface

**Base** (`backend/devboard/context_providers/base.py`):
- Provider type identification
- Context retrieval methods
- Strategy determination (EAGER/ON_DEMAND)
- URI validation (regex patterns)

**Available Providers**:
- **GitHub** (`github.py`): Repos, issues, PRs, commits. EAGER for small (issues/PRs), ON_DEMAND for large (repos)
- **Jira** (`jira.py`): Issues, projects, boards. EAGER for issues, ON_DEMAND for projects. Cloud/server support
- **Slack** (`slack.py`): Channels, threads. EAGER for threads, ON_DEMAND for history
- **Codebase** (`codebase.py`): Local/remote repos. EAGER for ARCHITECTURE.md/README, ON_DEMAND for full analysis
- **Web Page** (`webpage.py`): HTTP/HTTPS. EAGER for pages, ON_DEMAND for doc sites

## Loading Strategies

**EAGER**: Small, frequently accessed. Loaded into initial prompt. Examples: issues, PRs, tickets, arch docs, threads

**ON_DEMAND**: Large resources. Agent requests as needed. Reduces context size. Examples: full repos, codebases, doc sites, history

## URI Standards

**GitHub**: `https://github.com/{owner}/{repo}[/issues/{n}|/pull/{n}|/commit/{hash}]`

**Jira**: `https://{domain}.atlassian.net/browse/{KEY-N}` | `/projects/{KEY}`

**Slack**: `https://{workspace}.slack.com/archives/{channel}[/p{timestamp}]`

**Codebase**: `file:///{path}` | `git://github.com/{owner}/{repo}`

## Resource Validation

**Service**: `backend/devboard/services/resource_service.py`

**Process**:
1. Provider discovery (URI pattern match)
2. URI format validation (provider regex)
3. Resource accessibility test
4. Database record creation
5. Project linking with auto-detection

**Errors**:
- UnsupportedResourceUriError: No provider match
- ContextProviderUnavailable: Not configured

## Assembly Process

**ContextAssemblyService** (`context_assembly.py`):
1. **Categorize**: Separate EAGER vs ON_DEMAND
2. **Parallel Load**: Fetch EAGER resources concurrently
3. **Package**: Combine project/task resources + EAGER + ON_DEMAND list
4. **Format**: Structure for agent consumption

**Package Structure**:
- Project: spec, linked resources, codebase summaries, tasks
- Task: spec, implementation plan, parent project, task resources
- Query: conversation history, state, tools
- On-Demand: Available resource list

## Task Context Assembly

**Location**: `backend/devboard/agents/roles/context_helpers.py`

**`build_task_context()`** assembles standardized context for all task-related agent roles:

1. Task metadata (ID, name, status, PR number)
2. Project metadata (name, description)
3. Project specification (optional, controlled by `include_project_specification` flag)
4. PR status (optional, for PR review role)
5. Task specification
6. Implementation plan (structured or legacy Document format)
7. Custom fields (if present)
8. Codebase info (name, repo URL, worktree directory, description)

### Implementation Plan Context

The context helper supports two plan formats:

**Structured plan** (`ImplementationPlan` model): Preferred format. Renders plan overview and step list with statuses/types/dependencies. Step outcomes are controlled by the `include_step_outcomes` flag — omitted by default, included in full for roles that need execution history (StepExecution, CodeReview, TaskPRReview). Additionally includes an **execution graph** (`build_execution_graph_context()`) showing topological layers of steps that can run in parallel, with current status of each step.

**Legacy Document plan**: Falls back to rendering the Document content as markdown if no structured plan exists.

The structured plan format is automatically selected when `task.implementation_plan_structured` is present.

### Context Breakdown by Agent Role

`build_task_context()` is used by all task-related agent roles with per-role flag customization:

**Default context** (all roles): task metadata, project metadata, project specification, task specification, implementation plan summary (steps with status/type/dependencies), execution graph, custom fields, codebase info.

| Agent Role | `include_step_outcomes` | `include_project_specification` | `pr_status_content` | Notes |
|---|---|---|---|---|
| TaskPlanningRole | `False` | `True` | — | Steps haven't been executed yet; use `read_implementation_step_details` tool for step details on demand |
| TaskImplementationRole | `False` | `True` | — | Gets outcomes from `execute_implementation_step` return values; use `read_implementation_step_details` for step details on demand |
| StepExecutionRole | `True` | `True` | — | Needs prior step outcomes for context continuity |
| CodeReviewRole | `True` | `True` | — | Understanding step results helps assess implementation intent |
| TaskPRReviewRole | `True` | `True` | PR status string | Understanding step results helps respond to PR feedback |

## Caching

**Type**: In-memory cache-aside with TTL

**TTL**: 5 minutes (configurable)

**Key**: Resource URI + provider type

**Benefits**: Reduced API calls, faster response, lower costs, improved reliability

## Error Handling

**Exceptions** (`backend/devboard/context_providers/__init__.py`):
- ContextProviderUnavailable: Not configured
- NoProviderFound: No URI match
- UnsupportedResourceUriError: Invalid format

**Graceful Degradation**: System continues with available providers, structured logging

## Files

**Core**: `backend/devboard/services/{context_assembly.py, resource_service.py}`

**Providers**: `backend/devboard/context_providers/{base.py, github.py, jira.py, slack.py, codebase.py, webpage.py, registry.py}`

**Integrations**: `backend/devboard/integrations/`
