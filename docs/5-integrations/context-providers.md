# Context Providers

**Navigation**: [Documentation Home](../INDEX.md) > [Integrations](./INDEX.md) > Context Providers

**Purpose**: Gather and normalize external data (GitHub, Jira, Slack, codebases, web) for agents

**Location**: `backend/devboard/context_providers/`

## Architecture

**Base** (`base.py`): Interface requiring provider type, context retrieval, loading strategy (EAGER/ON_DEMAND), URI validation

**Key Pattern**: URI regex matching → provider selection → data fetching → normalization

## Providers

### GitHub (`github.py`)

**URIs**: `github.com/{owner}/{repo}[/issues/{n}|/pull/{n}|/commit/{hash}]`

**Strategy**: EAGER (issues, PRs, commits) | ON_DEMAND (repos, history)

**Context**: Issues (title, body, comments, labels), PRs (description, files, reviews), Repos (README, structure)

### Jira (`jira.py`)

**URIs**: `{domain}.atlassian.net/browse/{KEY-N}` | `/projects/{KEY}`

**Strategy**: EAGER (issues) | ON_DEMAND (projects, boards)

**Context**: Issues (summary, description, status, assignee, comments, custom fields), Projects (issues, workflows)

**Note**: Cloud and server support

### Slack (`slack.py`)

**URIs**: `{workspace}.slack.com/archives/{channel}[/p{timestamp}]`

**Strategy**: EAGER (threads) | ON_DEMAND (channel history)

**Context**: Threads with user IDs, timestamps, reactions, attachments

### Codebase (`codebase.py`)

**URIs**: `file:///path` | Registered codebase IDs

**Strategy**: EAGER (ARCHITECTURE.md, README) | ON_DEMAND (full analysis)

**Context**: Architecture summary (template-based), file structure, git history

### Web Page (`webpage.py`)

**URIs**: Any HTTP/HTTPS

**Strategy**: EAGER (specific pages) | ON_DEMAND (doc sites)

**Context**: Cleaned text, metadata, structure (HTTPx + BeautifulSoup4)

## Loading Strategies

**EAGER**: Load immediately, include in initial context. Use for small resources (issues, PRs, tickets, docs)

**ON_DEMAND**: List as available, agent requests as needed. Use for large resources (repos, codebases, doc sites, history)

## URI Validation

**Pattern Matching**: Regex per provider extracts identifiers (owner/repo, project/key, workspace/channel)

**Example Patterns**:
- GitHub: `^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)$`
- Jira: `^https://([^/]+)\.atlassian\.net/browse/([A-Z]+-\d+)$`
- Slack: `^https://([^.]+)\.slack\.com/archives/([^/]+)/p(\d+)$`

## Registry & Errors

**Registry** (`registry.py`): Provider discovery (URI matching, first match wins), instantiation, caching

**Exceptions** (`__init__.py`):
- ContextProviderUnavailable: Not configured
- NoProviderFound: No URI match
- UnsupportedResourceUriError: Invalid URI

**Graceful Degradation**: System continues with available providers

## Context Assembly

**Service** (`backend/devboard/services/context_assembly.py`):
1. Categorize by strategy
2. Select providers
3. Parallel fetch EAGER
4. Package context
5. List ON_DEMAND references

**Multi-Provider**: Combined context, unified format, source attribution

## Files

**Providers**: `backend/devboard/context_providers/{base.py, github.py, jira.py, slack.py, codebase.py, webpage.py, registry.py}`

**Services**: `backend/devboard/services/{context_assembly.py, resource_service.py}`

**Integrations**: `backend/devboard/integrations/`