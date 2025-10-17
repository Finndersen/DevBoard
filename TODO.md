- Change ContextProviderResource to have M2M links to projects and tasks, so they can be re-used.
- More consistent approach for initialising Integrations, maybe caching instances in registry or service
- More advanced codebase understanding process of creating summaries of individual files, then provide to agent to build full architectural document
- Add Sentry and Datadog integrations: https://docs.sentry.io/api/events/list-an-organizations-issues/
- add parametrization to template service
- Allow customising templates through frontend UI
- OAuth integrations (either direct or via remote MCP server)
- Unified MCP server management UI in frontend, with ability to choose tools/resources
- Daily update/briefing of new Slack content, task updates, etc
- custom slash commands for project agent for custom workflows (e.g. use Datadog to translate transaction ID to trip ID) 
- General purpose AI-Powered "Rubber Ducking" & Debugging Partner
- To-Do list (project or global level)
- Show unified diff view by default when showing code changes
- allow configuring which patterns to exclude from directory tree view
- Integrate memory (maybe with https://github.com/mem0ai/mem0)
- Change implementation of Project Specification toa more complex Documentation system which is filesystem git-based, for automatic version control, and can be pushed to remote repo for collaboration/sharing. Can be linked to standalone doucmentation repo, or within a codebase repo
- streaming: Initially just stream final result content using agent.run_stream(), then can stream tool calls etc as well as final content using agent.run_stream_events() (for PydanticAI)
- Handle CladueCOde error responses like: API Error: 404 {"type":"error","error":{"type":"not_found_error","message":"model: claude-sonnet-4.5"},"request_id":"req_011CU9vQ1DSP73cZHsQ62QNL"}


For Implementation agent:
- Add interface for viewing & editing user-level CLAUDE.md agent prompt/context file
- Add interface for viewing & editing user-level Claude custom commands
- Add interface for viewing & editing user-level Claude MCP server config