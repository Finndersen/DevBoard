Project Specification: “DevBoard”

Overview
I want to build a "developer command centre" application which acts as a project & task management system and AI project management & developer assistant/co-pilot. It can integrate with Slack, Jira, Notion etc to ingest context about the project and tasks, which it can provide to AI developer agents to assist with development and delivery of tasks. The user can query and update about project and task status. 

It will run locally on the users machine, and will need some kind of user interface as well as backend and database for storing state and probably running async background jobs.

Will involve primary/native integrations that are more essential for operation and support read/write operations, and can act as context providers:
Task management integration (e.g. Jira, Asana) - for linking with tasks and providing context about project status and other tasks being worked on by other people
Code repository integration (e.g. Github) - for creating/managing PRs 
As well as additional more basic read-only context providers, e.g. Notion, google docs, document files, web page,  etc.

Will leverage existing CLI AI agents like Claude Code or Gemini CLI to perform agential context gathering or task implementation. Will need some way to wrap their execution and allow user to see somewhat realtime update of output as well as provide input ( Claude Code SDK is probably good for this). Will also need some way of providing context and managing conversation history, as well as dynamic configuration of MCP servers etc. 
Also might want to have some kind of wrapper script that allows launching an interactive CC/ Gemini CLI session directly linking it with context and conversation history of a task

Logical Objects/Entities
Project
High-level representation of a relatively large piece of work (analogous to a Jira epic). 
Will have associated context providers for supplying background information and status updates for project (e.g. Slack channel, Jira/Asana board/epic, Notion page/space, documents, user-provided text content)
Will have a Project Details document, with overview of project and technical details, possibly with links to external resources (Where/how will this be stored and potentially shared between collaborators?)
Task
Represents a self-contained piece of work (analgous to and will often be linked to a Jira/Asana task)

Attributes:
Status - i.e. “pending / in progress / review / complete” that is linked and synced to Jira/Asana task
Description -  that can be entered manually by user or retrieved from linked remote task and then be updated
Link to Project
associated Jira/Asana task ID
Relevant Github repos/codebases
Relevant github PR (set after initial task implementation)
Coding agent conversation ID (to link with conversation history of Claude Code/Gemini to allow resuming sessions)
Assigned person (to facilitate potential collaboration features)
Will also need some way of viewing and managing the progress of implementation agent when executing task, such as tracking sub-task status 
Context Provider
An interface for providing context relevant to a particular project, task or codebase, from some external resource or data source.
Will have a generic interface, with implementations for different kinds of data sources or integrations (e.g. Slack, Jira, Notion, docs,  Github). 
Will require some form of configuration specific to the context provider type for connection details, credentials, other config etc.
Could either manually associate a context provider “instance” of a particular type (e.g. Slack channel link, Notion page URL) with Projects or tasks, OR automatically detect and handle links/URLs/addresses provided in Project/task descriptions 
Small-scale resources (speciifc Slack message, Jira task, Github PR, webpage, etc) can have content automatically retrieved and provided verbatim without agent needing to do itself.
Larger-scale resources (Slack channel, Notion page, PDF document, etc) could be configured with a description and provided to agent as an available resource that it can choose to query to get condensed context relevant to query
API:
can_handle_uri(resource_uri) - Whether this context provider is able to handle a URI (link to some kind of resource)
get_resource(resource_uri) - Retrieve the data for a particular small-scope resource (e.g. single Slack message, single Jira task, single file, single doc/Notion page/webpage) 
this can be quite straightforward and just return the data as-is
get_relevant_context(resource_uri, query) - Retrieve context/detail relevant to a specific query or task, from a larger-scope (project-level) resource (Entire Slack channel, Jira Epic/board, large documents, codebase) 
Could either use RAG, or just feed entire resource content into high-context-window LLM (Gemini), get it to summarise or extract specific content relevant to a given query or task. 
For complex resource like a Slack channel, the context provider would need some kind of mechanism for tracking/storing message data and updating content incrementally over time instead of re-reading from scratch (need to store state in DB/file)
For something really massive and complex like a codebase, could maintain a high level project structure and have an AI agent interactively search using tools to get context
get_mcp_tools() - Returns a list of tools specific to this context provider that will be provided  to task Planning or Implementation agents to enable dynamic access to resources. Relevant tools from all context providers will be merged into a unified MCP server which will be configured for AI agents.
 OR, returns configuration details of an existing MCP server relevant to the context provider
update_content() - Perform a refresh of local cached content for a large-scope resource (Entire Slack channel, Jira Epic/board) 

Codebase
A software codebase relevant to a project or task. 
A project could potentially have multiple relevant codebases, however for simplicity may be best to restrict each task to a single codebase
Could theoretically support multiple codebases per Github repository (for monorepo setups), but maybe initially have a 1-to-1 mapping for simplicity
Effectively acts as a special case context provider/integration
Have an associated Overview/Architecture document to describe codebase layout, important classes/modules/functions, patterns, design, etc. Could be stored as a markdown file in the codebase repository so it can be version controlled.

Agents
Different types and tiers of AI agents:
Project-level Q&A agent
Fast & cheap model with large context window like Gemini Flash
Should it be 1-shot Q&A or more conversational? Harder to continue to include relevant project context with conversational style, don’t want to do retrieval for every message. Could maybe have a “retrieve_relevant_project_context()” tool that the agent can use to decide when it needs more porject info instead of doing automatically?
Provided with list of configured context providers or large-scale resources available, with associated descriptions (e.g. Project Slack channel, Notion page with project docs, PDF file with interface specification, codebases). Then agent can query them for relevant context as required
Is always provided project overview/details docunent with status and  visibility of all ( or at least active and recent) tasks. 
Has tools for:
Exploring/reading relevant linked resources from context providers
Reading more details & state of individual tasks
Updating project details/summary and status
Should entire conversation history be conserved? Or should conversations be more transient? Probably easiest to keep as somewhat transient, to prevent context buildup and congestion
Can run in app within API request using framework like PydanticAI
Context Provider Investigation Agents
Context providers may choose to use agential investigation/search to implement get_relevant_context() API (effectively acting as a sub-agent), e.g.
Searches Slack channel for details relevant to query
explores Notion docs following links
Searches/reads a large PDF / text document
Explores a website/webpage following links
Fast & cheap model with large context window like Gemini Flash
Can initially run in app within API request using framework like PydanticAI, may need to offlload to background task
Task Investigation & Planning agent
Is provided with:
task description
content of any linked small-scale resources
Project summary/details and current status
details of any linked/associated larger scale project or task-level context provider resources (which it can choose to query)
Summary/details of associated codebase (automatically do agential codebase investigation for relevant details and provide to Investigation agent, or let agent trigger it as needed? - I think latter)
Decides what content to retrieve from large-scale resources
Asks any clarification questions
Produces detailed implementation plan with enough granularity to facilitate implementation without further research/investigation
Users can  conversationally review, update and approve implementation plan
Requires intelligent, thinking model with large context window like Gemini Pro
Can  run in app as background task/job using framework like Pydantic AI
Task Implementation Agent
Is provided Task description and Implementation plan (whcih should also contain all relevant context and details required to implement)
Implements changes in codebase, runs checks and tests
Can pick up and continue conversation to iterate/collaborate on task implementation, including in response to Github PR review comments etc
Requires agent with strong agential / tool use capabilities such as Claude (using Claude Code SDK)
Post-tast-completion review agent
Reviews the outcome of a task implementation process, to make any necessary updates to:
Project details or status
Codebase details/architecture document (can be included as part of the task changes PR)
User and Codebase-level prompt guidelines (e.g. CLAUDE.md file) to help avoid any challenges/mistakes/pitfalls that implementation agent encountered



Architecture / Tech Stack
Probably makes sense to go with a web-based client server architecture, with a locally running web server and browser UI.

Run everything in container, or install globally on user local system?
Would probably want local filesystem access to work on code repositories - could explicitly mount them into container?
May want to have SSE or websockets to support streaming or real-time bidirectional communication?
Backend
Python-based backend webserver and MCP server as APIs to the system state and context provider integrations.
Async FastAPI web server
SQLAlchemy for data modelling probably just with local SQLite DB - depending on concurrency needs
Context Provider abstraction/interface with different class implementations for each type
Abstractions for running/interfacing with Claude Code or Gemini CLI agents
Some operations will be long-running - could initially just perform most within API request, but may need to have some kind of background async task execution framework (Especially for AI agent execution which could run for a long time - but would need some way of feeding I/O to UI)
Frontend

Web-based UI probably using some common framework like React
Would a Jira/Asana board style interface with status columns and task cards make sense? 
Or maybe a tabbed interface with “Backlog”, “In Progress” and “Complete” tabbed views with tasks listed as more horizontal oriented cards?


Features / User Workflow
Global
Phase 1
UI for viewing/editing Claude Code custom slash commands
UI for viewing/editing user-level Claude Code CLAUDE.md prompt guidance file
UI for managing MCP server configuration (to be provided to task panning & implementation agents)
Phase 2
Unified MCP server which provides integrations to configured context providers to Implementation agent

Context Providers
Phase 1
Integrations & context providers for Slack, Github, Jira, Notion, Document (e.g. PDF)
Basic approach for handling large-scale context provider resouces e.g. Slack Channel, use built-in Seach capabilities
Phase 2
More sophisticated large-scale context provider resource handling, like generating summaries/indexes of converstaions within a Slack channel for faster local retieval (probably only necessary if native search capabilties don’t work as well)
Project
Phase 1
Project view with description and status (could be a single markdown format text content or more dynamic), which can be automatically updated after completion of each task
Project-level chat interface (Q&A agent) to allow asking questions about project status or anything from context providers
Phase 2
Can conversationally provide updates to project status (or read from Slack threads), which agent can use to update the “live” project status and trickle down to the more “static” project overview/details document
Task
Phase 1
Add new task either from Jira/Asana ID or create manually. Provide as much detail/context as possible, with links to resources, relevant codebase
Can trigger investigation/planning phase, where context is gathered from all task and relevant project-level context providers, fed to planning agent which can do more dynamic agential research if required and generate an implementation plan for review
implementation plan can be modified manually or interactively using agent chat interface
Once ready, user can trigger implementation agent to begin (or could allow doing directly from CLI via wrapper which causes the agent session to be linked to the task with plan and context). 
Ideally have a nice way of visualising sub-task status (including parallelism of sub-agents) and agent tool use (try parse raw Claude conversation logs or need some other way to get detail? Claude Code SDK?)
After implementation is complete, can trigger agent/special custom workflow to create PR 
Phase 2
Detailed display of implementation agent activity with sub-task/agent and tool use visualisation/inspection 
Can continue conversation with implementation agent during PR lifecycle to respond to feedback, automatically provide linked Github PR comments (or allow to retrieve)
When task is complete, have an agent which reviews the outcome to reconcile learnings:
Update project status / details
Suggest updates to impementation agent prompt guidance config

CLI
Phase 2
CLI command for:
Starting a Claude Code / Gemini interactive session for a particular task, or for project (automatically provides relevant context, or resumes previous conversation associated with task)
Triggering particular workflow steps for a task (plan, implement, review, create PR, etc)

Multi-User Collaboration
Phase 3
Project and task data is somehow synced between multiple users working on the project

Unknowns to Clarify/Answer
Best methods for interfacing with context providers (e.g. Slack, Github, Jira, Notion) via Python (SDK libraries?) running from local machine - May not have permissions to create a new Slack app for Oauth. Could also potentially wrap existing MCP servers, but that is probably an extra unnecessary layer of interface and abstraction
How to manage a potentially long-running background task (e.g. for Planning or Implementation agent) and feed/stream output back to frontend UI? 
For implementation agent, will I need to manage conversation history and resuming myself, or just leverage Claude Code built in capability?
Front-end UI layout & style?
