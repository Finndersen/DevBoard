# External Services

**Navigation**: [Documentation Home](../INDEX.md) > [Integrations](./INDEX.md) > External Services

**Purpose**: API clients for GitHub, Jira, Slack with auth, rate limiting, error handling

**Location**: `backend/devboard/integrations/`

**Pattern**: Integrations handle API communication; context providers normalize data

## Integrations

### GitHub (`github.py`)

**Client**: PyGithub

**Auth**: `GITHUB_ACCESS_TOKEN` (personal access token)

**Capabilities**: Repo info, issues (details + comments), PRs (description + files + reviews), commits, file structure

**Rate Limit**: 5,000 requests/hour (authenticated), aware via headers, auto-backoff

### Jira (`jira.py`)

**Client**: Jira Python SDK

**Auth**: `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (Basic auth, Base64)

**Capabilities**: Issues (expandable fields + custom fields + comments), projects, workflows, attachments

**Support**: Cloud and server (configurable base URLs)

**Rate Limit**: Varies by plan/config, error detection

### Slack (`slack.py`)

**Client**: Slack SDK

**Auth**: `SLACK_BOT_TOKEN` (OAuth bot token as Bearer)

**Capabilities**: Conversation history, thread replies, channel info, user identification, threading preservation

**Rate Limit**: Tier-based, method-specific, exponential backoff retry

## Architecture

**Separation**: Integrations = API communication, Context Providers = data processing/normalization

**Graceful Degradation**: System continues when optional integrations unavailable

**Configuration**: Instantiated based on available credentials

## Authentication

**Credentials** (primary: env vars):
- `GITHUB_ACCESS_TOKEN`
- `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- `SLACK_BOT_TOKEN`

**Alternative**: ConfigService database storage

**Security**: Never exposed in logs or API responses

**Patterns**:
- GitHub: Token in Authorization header
- Jira: Basic auth (email + API token, Base64)
- Slack: OAuth Bearer token

## Integration Registry

**Location**: `backend/devboard/integrations/registry.py`

**Responsibilities**: Factory (create instances from credentials), config management, availability checking, graceful fallbacks (None for unavailable)

**Dependency Injection** (`backend/devboard/api/dependencies/services.py`): Optional dependencies, services adapt to None

## Error Handling

**Types**:
- **Auth**: Invalid credentials, expired tokens, insufficient permissions
- **API**: Rate limit, resource not found, invalid requests, server errors
- **Network**: Timeouts, DNS failures, unavailability

**Patterns**: Structured exceptions, detailed messages, comprehensive logging, graceful degradation (reduced functionality)

## Rate Limiting

**Strategies**:
- **Awareness**: Check rate limit headers
- **Throttling**: Slow down when approaching limits
- **Caching**: Frequently accessed data
- **Error Handling**: Graceful with user notification

**GitHub**: 5K/hour, backoff when approaching

**Jira**: Cloud varies, server configurable, error detection

**Slack**: Tier-based, method limits, exponential backoff

## HTTP Client

**Library**: HTTPx async

**Features**: Connection pooling, timeout config, retry logic, request/response logging

## Testing

**Location**: `backend/devboard/api/routers/settings.py`

**Endpoints**:
- `POST /api/settings/integrations/github/test`
- `POST /api/settings/integrations/jira/test`
- `POST /api/settings/integrations/slack/test`

**Process**: Accept credentials → simple API call → return success/failure + error → never auto-persist

## Usage Flow

1. Context provider requests data for URI
2. Select integration
3. Authenticated API call
4. Process response
5. Return normalized data
6. Structured exceptions on error

## Files

**Integrations**: `backend/devboard/integrations/{github.py, jira.py, slack.py, codebase.py, shell.py, registry.py, base.py}`

**Dependencies**: `backend/devboard/api/dependencies/services.py`

**Config**: `backend/devboard/config/integration_configs.py`, `backend/devboard/services/config_service.py`

**Testing**: `backend/devboard/api/routers/settings.py`

## See Also

[Context Providers](./context-providers.md) | [Context Assembly](../4-ai-agents/context-assembly.md)
