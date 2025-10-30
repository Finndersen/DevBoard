# Documentation Maintenance Guide

**Navigation**: [Documentation Home](./INDEX.md) > Maintenance Guide

## Purpose & Philosophy

This guide serves as a **system prompt for AI agents** and a reference for human contributors on how to create and maintain the DevBoard documentation structure. Following these guidelines ensures consistent, up-to-date, and navigable documentation.

### Why This Documentation Exists

- **Serve Humans AND AI Agents**: Documentation must be readable by both audiences
- **Concise & Focused**: Each file covers a single topic or closely related concepts
- **High Information Density**: Maximum useful information, zero fluff
- **Cross-Referenced**: Documents link to related content for easy navigation
- **Minimal Duplication**: Information exists in one canonical location
- **Up-to-Date**: Documentation evolves with the codebase
- **Point to Code**: Reference code locations, don't duplicate implementation details

### Target Audiences

- **Developers**: Understanding codebase structure and implementation patterns
- **Product Managers**: Learning features and capabilities
- **AI Agents**: Loading focused context for specific tasks
- **Contributors**: Maintaining and extending documentation

## Structure Guidelines

### File Size Limits

- **Target**: 100-200 lines per file
- **Hard Maximum**: 300 lines
- **Exception**: INDEX.md files and MAINTENANCE_GUIDE.md

When documents approach 250 lines, consider splitting into subdirectory with INDEX.

### When to Split Documents

**Signals that splitting is needed**:
- File exceeds 300 lines
- Document covers multiple distinct subtopics
- Difficult to find specific information
- Table of contents has 10+ items

**How to split**:
1. Analyze content for logical boundaries
2. Create subdirectory with INDEX.md
3. Split into focused sub-documents (e.g., `agent-architecture.md` → `agents/INDEX.md`, `agents/base-agent.md`, `agents/roles.md`)
4. Update parent INDEX to reference subdirectory
5. Update all incoming links to new locations

### Fractal Organization Pattern

Documentation structure is **self-similar at different scales**:

```
docs/
├── INDEX.md (overview)
├── 1-overview/
│   ├── INDEX.md (section overview)
│   └── [documents]
├── 3-architecture/
│   ├── INDEX.md (section overview)
│   ├── backend/
│   │   ├── INDEX.md (subsection overview)
│   │   └── [documents]
│   └── [documents]
```

Same pattern repeats at each level: INDEX.md + focused documents.

### Directory Naming Conventions

- **Numbered for Priority**: `1-overview/`, `2-features/`, `3-architecture/` (indicates reading order)
- **Kebab-Case**: `agent-architecture.md`, `context-providers.md`
- **Descriptive**: Name clearly indicates content (`getting-started.md` not `setup.md`)

### File Naming Conventions

- **Kebab-Case**: All lowercase with hyphens (`task-management.md`)
- **Descriptive**: Immediately clear what document covers
- **Specific**: `agent-architecture.md` better than `agents.md`
- **Avoid Abbreviations**: `configuration.md` not `config.md` (unless abbreviation is standard)

## Document Format Standards

### Required Sections for Content Documents

**Navigation Breadcrumbs** (first line):
```markdown
**Navigation**: [Documentation Home](../INDEX.md) > [Section](./INDEX.md) > Document Title
```

**Heading Structure**:
- `# Title` (once, document title)
- `## Main Sections` (major topics)
- `### Subsections` (details within topics)
- `#### Sub-subsections` (use sparingly)

**See Also Section** (where relevant):
```markdown
## See Also

- [Related Doc 1](../path/to/doc.md): Brief context
- [Related Doc 2](./another-doc.md#section): Link to specific section
- [Code Reference](../3-architecture/backend/components.md): Implementation details
```

### INDEX.md Document Structure

Every directory must have an INDEX.md with:

```markdown
# Section Title

**Navigation**: [Documentation Home](../INDEX.md) > Section

## Purpose

Brief description of section's scope and content.

## Documents

### [Document Title](./document.md)
Brief description of what document covers.

### [Another Document](./another.md)
Brief description of content.

## Related Sections

- [Related Section](../other-section/INDEX.md): Context
```

### Code Reference Format

**DO**: Reference code locations
```markdown
**Location**: `backend/devboard/services/task_service.py`
See [Backend Components](./components.md#services) for overview.
```

**DON'T**: Copy code snippets
```markdown
<!-- AVOID THIS -->
```python
def task_service():
    # ...actual code...
```
<!-- END AVOID -->
```

**Exception**: Short examples (5-10 lines) to illustrate patterns are acceptable.

## Content Guidelines

### High Information Density Principle

**Every sentence must provide unique, valuable information**. Remove:
- Generic statements that apply to any system ("uses HTTP", "returns JSON")
- Obvious implementation details visible in code ("uses class inheritance")
- Redundant explanations of standard concepts ("REST uses GET/POST/PUT/DELETE")
- Low-level details that change frequently and burden maintenance

**Focus on**:
- Unique architectural decisions and why they were made
- Key entities/models/classes and where to find them
- Non-obvious relationships between components
- High-level patterns that guide implementation

### Write for Both Humans and AI

- **Clear and Direct**: Active voice, present tense
- **Context First**: Explain "why" before "how"
- **Examples Sparingly**: Only when pattern is non-obvious
- **Structured Information**: Use headings, lists, tables appropriately

### Focus on "What" and "Why", Reference for "How"

**Good** (High density, points to code):
```markdown
## Task Lifecycle

Tasks use a six-state lifecycle with state-specific agent roles. State transitions trigger agent configuration updates.

**States**: DEFINING → DESIGNING → PLANNING → IMPLEMENTING → IN_REVIEW → COMPLETE

**Key Implementation**: `TaskRepository.transition_state()` validates allowed transitions and updates conversation agent.

**Location**: `backend/devboard/db/models/task.py`, `backend/devboard/services/task_service.py`
```

**Avoid** (Low density, generic, too detailed):
```markdown
<!-- Too verbose, generic, implementation detail -->
## Task Lifecycle

Tasks in DevBoard progress through a lifecycle. This lifecycle helps organize work and ensures proper workflow management.

Tasks start in the DEFINING state when first created. Users can then transition them to DESIGNING where they work with the specification agent. After designing, tasks move to PLANNING where the planning agent helps create an implementation plan. Then tasks move to IMPLEMENTING where code is written. After implementation, tasks move to IN_REVIEW for code review. Finally, tasks reach the COMPLETE state when finished.

The Task model inherits from Base and uses SQLAlchemy's declarative_base() with mapped columns. The state field uses an Enum type with six values...
[continues with ORM details]
```

### What NOT to Document

**Avoid documenting**:
- Generic tech stack features ("FastAPI supports async", "React uses components")
- Standard HTTP status codes or REST conventions
- Pydantic/SQLAlchemy/React patterns available in official docs
- Low-level implementation details visible in code (parameter types, inheritance hierarchies)
- Boilerplate patterns (CRUD operations, standard error handling)

**Instead document**:
- Why this tech was chosen and key non-standard usage
- DevBoard-specific patterns and conventions
- Architectural decisions and tradeoffs
- Non-obvious relationships between components

### Link to Source Code Locations

Always provide path to implementation:
- `backend/devboard/agents/base_agent.py`
- `frontend/src/components/chat/ConversationChat.tsx`
- `backend/devboard/db/models/`

### Avoid Duplication

**Single Source of Truth**: Each piece of information should exist in exactly one place.

**Cross-Reference Instead of Duplicate**:
```markdown
<!-- GOOD -->
Tasks support external resource linking. See [Context Providers](../5-integrations/context-providers.md) for details on resource types.

<!-- BAD: Duplicating content -->
Tasks support external resource linking. Resources can be GitHub repos, Jira tickets, Slack threads... [repeating content that exists elsewhere]
```

### Keep Content Evergreen

- **Avoid**: "currently", "recently", "will soon", "in the future"
- **Use**: Present tense for existing features, explicit "Future" sections for roadmap

**Good**:
```markdown
DevBoard supports three LLM providers: OpenAI, Anthropic, and Google.

### Future Enhancements
- Azure OpenAI integration
- Custom model support
```

**Avoid**:
```markdown
DevBoard currently supports OpenAI and recently added Anthropic support. Google Gemini will be added soon.
```

## Linking Best Practices

### Relative Markdown Links

**Always use relative paths**:
```markdown
[Task Management](../2-features/task-management.md)
[Backend API](./backend/api-reference.md)
[Same Directory](./other-doc.md)
```

**Never use absolute URLs** for internal docs.

### Descriptive Link Text

**Good**:
```markdown
See [Agent Configuration](../4-ai-agents/configuration.md) for model selection details.
```

**Bad**:
```markdown
See [here](../4-ai-agents/configuration.md) for details.
Click [this link](./doc.md) to learn more.
```

### Anchor Links for Sections

Link to specific sections when relevant:
```markdown
[Task States](./task-management.md#task-lifecycle)
[Database Schema - Conversation Model](./database-schema.md#conversation-model)
```

### Bidirectional Linking

If Document A references Document B, consider if Document B should reference Document A:
```markdown
<!-- task-management.md -->
See [Agent Architecture](../4-ai-agents/agent-architecture.md) for agent role details.

<!-- agent-architecture.md -->
See [Task Management](../2-features/task-management.md) for how roles support task workflows.
```

### Test Links Work

- **GitHub**: Links work in GitHub web interface
- **VSCode**: Cmd+Click navigation works
- **Relative Paths**: Survive repository moves/renames

## Update Workflows

### When Code Changes: Update Relevant Architecture/Implementation Docs

**Trigger**: Significant code changes (new features, refactoring, architecture changes)

**Process**:
1. Identify affected documentation files
2. Update relevant sections maintaining document structure
3. Verify no content duplication introduced
4. Check cross-references still accurate
5. Ensure file stays under 300 lines

**Example**: New API endpoint added → Update `backend/api-reference.md` and relevant feature doc.

### When Features Change: Update Feature Docs and Related Architecture

**Trigger**: Feature additions, modifications, or removals

**Process**:
1. Update feature document in `2-features/`
2. Update related architecture documents (API, components)
3. Update overview documents if core concepts changed
4. Add/update cross-references

### When Adding New Subsystems: Create New Section or Subdirectory

**Trigger**: New major component or subsystem

**Decision**:
- **New top-level section**: Rarely (only for major system areas like a new "7-plugins/" section)
- **New subdirectory**: More common (e.g., `3-architecture/agents/` if agent docs grow too large)
- **New document**: Most common (add to existing section)

**Process**:
1. Determine appropriate location in hierarchy
2. Create document(s) following naming conventions
3. Update parent INDEX.md
4. Add cross-references from related docs
5. Update root INDEX.md if new top-level section

### When Docs Exceed Size Limits: Split into Subdirectory

**Process**:
1. Create subdirectory (e.g., `agents/`)
2. Create `agents/INDEX.md` with section overview
3. Split original document into focused sub-documents
4. Update parent INDEX to reference subdirectory
5. Update all incoming links to new locations
6. Verify no content lost during split

**Example**:
```
Before: 4-ai-agents/conversation-system.md (350 lines)

After:
4-ai-agents/conversation/
├── INDEX.md (overview)
├── event-types.md (event definitions)
├── streaming.md (streaming architecture)
└── persistence.md (message storage)
```

### Quarterly Reviews: Check for Outdated Content

**Schedule**: Every 3 months

**Checklist**:
- [ ] Check for outdated content (references to removed features)
- [ ] Test all cross-reference links
- [ ] Verify code location references still accurate
- [ ] Look for opportunities to consolidate duplicate content
- [ ] Check file sizes (split if needed)
- [ ] Review for clarity and readability
- [ ] Update screenshots or examples if outdated

## Common Update Scenarios

### Scenario: New API Endpoint Added

**Files to Update**:
1. `3-architecture/backend/api-reference.md`: Add endpoint details
2. `3-architecture/api-design.md`: If introduces new pattern
3. Relevant feature doc in `2-features/`: Add user-facing capability
4. Add cross-references between feature → API → implementation

**Example**:
```markdown
<!-- 2-features/project-management.md -->
Projects support exporting to JSON format. See [API Reference](../3-architecture/backend/api-reference.md#export-project) for endpoint details.

<!-- 3-architecture/backend/api-reference.md -->
## Export Project

`GET /api/projects/{id}/export`

Exports project data as JSON. See [Project Management](../../2-features/project-management.md) for feature description.
```

### Scenario: New Agent Role Introduced

**Files to Update**:
1. `4-ai-agents/agent-architecture.md`: Add role description
2. `4-ai-agents/configuration.md`: Add configuration options
3. Relevant feature doc: Add user-facing capabilities
4. `1-overview/key-concepts.md`: If introduces new concept
5. Update code references

### Scenario: Technology Stack Change

**Files to Update**:
1. `3-architecture/system-design.md`: Update tech stack section
2. `6-development/getting-started.md`: Update prerequisites
3. Relevant backend or frontend docs: Update implementation details
4. `3-architecture/INDEX.md`: Update tech stack summary
5. Root `INDEX.md`: If significant change

### Scenario: Document Grows Beyond 300 Lines

**Process**:
1. Analyze content for logical split points
2. Create subdirectory with INDEX.md
3. Split content into focused sub-documents:
   ```
   conversation-system.md (350 lines) →
   conversation/INDEX.md (50 lines overview)
   conversation/event-types.md (100 lines)
   conversation/streaming.md (100 lines)
   conversation/persistence.md (100 lines)
   ```
4. Update parent INDEX to reference subdirectory
5. Update incoming links:
   ```markdown
   <!-- Old -->
   [Conversation System](./conversation-system.md)

   <!-- New -->
   [Conversation System](./conversation/INDEX.md)
   [Event Types](./conversation/event-types.md)
   ```
6. Verify no content lost

## Quality Checklist

Before considering documentation update complete:

- [ ] No file exceeds 300 lines
- [ ] All links are relative and working (test in GitHub and VSCode)
- [ ] Documents have "See Also" section where it adds value
- [ ] Code references point to actual files (not copied code)
- [ ] No duplicate content across multiple files
- [ ] Related documents reference each other bidirectionally
- [ ] INDEX files updated with new documents
- [ ] Heading hierarchy is consistent (# title, ## sections, ### subsections)
- [ ] Content is clear and concise
- [ ] Navigation breadcrumbs present

## AI Agent Behavior Instructions

**You are a documentation maintenance agent. Your purpose is to create and maintain the DevBoard documentation structure according to these guidelines.**

### When Creating New Documentation

**Research Phase (before creating)**:
1. Determine correct category based on content type:
   - Product/vision/concepts → `1-overview/`
   - User-facing features → `2-features/`
   - System architecture/implementation → `3-architecture/`
   - AI agent system details → `4-ai-agents/`
   - External integrations → `5-integrations/`
   - Development/setup guides → `6-development/`
2. Check if existing document can accommodate content (stay under 250 lines)
3. If creating new file, follow kebab-case naming convention
4. Identify related documents for cross-referencing

**Creation Phase**:
1. Extract content from source, do not copy verbatim - synthesize and organize
2. Add navigation breadcrumbs at top
3. Structure with appropriate headings (# title, ## sections, ### subsections)
4. Add cross-references to related documents in "See Also" section
5. Update parent INDEX.md with new document listing
6. Ensure no content duplication across files
7. Reference code locations, not code snippets

### When Updating Existing Documentation

**Research Phase (before making changes)**:
1. Load relevant existing documents to understand current state
2. Identify which specific sections need updates based on code changes
3. Check current document sizes to avoid exceeding 300-line limit
4. Note existing cross-references to preserve them
5. Identify potential duplication with other documents

**Update Phase**:
1. Make focused, minimal changes to specific documents only
2. Preserve existing structure, heading hierarchy, and formatting
3. Add new cross-references where they provide value
4. Update "See Also" sections if adding related content
5. Reference code locations, DO NOT copy code snippets
6. Use relative markdown links for all cross-references
7. Keep content evergreen (avoid "currently", "recently")

**Validation Phase (after making changes)**:
1. Count lines - verify document still under 300 lines (if over 250, consider splitting)
2. Test all links are valid relative paths with correct syntax
3. Verify no content duplication introduced across documentation
4. Confirm changes reflected in relevant INDEX files
5. Check heading hierarchy is consistent
6. Ensure code references point to actual file paths

### When Documents Exceed Size Limits

**Process**:
1. Analyze content for logical split points (distinct subtopics)
2. Create subdirectory with INDEX.md (e.g., `conversations/INDEX.md`)
3. Split content into focused sub-documents (100-200 lines each)
4. Update parent INDEX to reference new subdirectory
5. Update all incoming links to point to new file locations
6. Ensure no content is lost during split

## Style Guide

### Voice and Tense

- **Active Voice**: "The system manages tasks" not "Tasks are managed"
- **Present Tense**: "Agent executes tools" not "Agent will execute"
- **Second Person for Instructions**: "You can configure..." or "Load the document..."
- **Third Person for Descriptions**: "The agent analyzes..." not "We analyze..."

### Link Text

- **Descriptive**: "See [Agent Configuration](./config.md)" not "See [here](./config.md)"
- **Context in Text**: Provide brief context after link when helpful

### Formatting

- **Code Paths**: Backticks for file paths, code references, commands: `backend/devboard/agents/`
- **Bold for Emphasis**: Use **bold** for key terms on first use or emphasis
- **Italics Sparingly**: Use *italics* minimally, only for specific emphasis
- **Lists**: Bullet lists for related items, numbered lists for sequences
- **Tables**: Use for structured comparisons or reference data

### Code Blocks

Use code blocks for:
- **Examples**: Short examples illustrating patterns (5-10 lines)
- **API Requests/Responses**: JSON examples
- **Configuration**: YAML, environment variables
- **Commands**: Shell commands with proper formatting

```markdown
```bash
# Good: Example command with comment
uv run pytest tests/
```
```

### Lists

**Bullet Lists** for unordered items:
```markdown
- First item
- Second item
- Third item
```

**Numbered Lists** for sequences:
```markdown
1. First step
2. Second step
3. Third step
```

**Nested Lists** for hierarchy:
```markdown
- Category
  - Item 1
  - Item 2
- Another category
  - Item A
  - Item B
```

## Templates

### INDEX.md Template

```markdown
# Section Title

**Navigation**: [Documentation Home](../INDEX.md) > Section

## Purpose

Brief description of this section's scope and content (2-3 sentences).

## Documents

### [Document Title](./document-name.md)
Brief description of what this document covers (1-2 sentences).

### [Another Document](./another-doc.md)
Brief description of content (1-2 sentences).

## Related Sections

- [Related Section](../other-section/INDEX.md): Context about relationship
```

### Content Document Template

```markdown
# Document Title

**Navigation**: [Documentation Home](../INDEX.md) > [Section](./INDEX.md) > Document Title

## Overview

Brief introduction to topic (1-2 paragraphs). What this document covers and why it matters.

## Main Section

Content organized under clear headings.

### Subsection

Detailed content with examples where helpful.

**Location**: `backend/path/to/implementation.py`

## Another Main Section

Continue organizing content logically.

## See Also

- [Related Doc](../path/to/doc.md): Brief context
- [Another Doc](./other.md): Relationship explanation
- [Implementation](../3-architecture/backend/components.md): Technical details
```

### "See Also" Section Template

```markdown
## See Also

- [Related Concept](../1-overview/key-concepts.md#concept): Domain model definition
- [Feature Description](../2-features/feature.md): User-facing capabilities
- [Implementation](../3-architecture/backend/components.md): Technical implementation
- [API Reference](../3-architecture/backend/api-reference.md#endpoint): API endpoints
```

### Code Reference Template

```markdown
**Purpose**: What this component does.

**Key Capabilities**:
- Capability 1
- Capability 2
- Capability 3

**Location**: `backend/devboard/module/file.py`

See [Related Documentation](./related.md) for more context.
```

## Maintenance Examples

### Example: Updating After Code Change

**Scenario**: New `search_codebase` tool added to agents.

**Changes Made**:
```markdown
<!-- 4-ai-agents/tools-and-capabilities.md -->
## Available Tools

### search_codebase

Semantic and keyword search across registered codebases.

**Arguments**:
- `query`: Search query (string)
- `codebase_id`: Optional codebase to search

**Location**: `backend/devboard/agents/tools.py`

<!-- Also update -->
- 2-features/codebase-documentation.md: Add user capability
- 4-ai-agents/agent-architecture.md: Update tool list
```

### Example: Creating New Document

**Scenario**: Adding `web-api-integration.md` to integrations.

**Process**:
1. Create `docs/5-integrations/web-api-integration.md`
2. Add content following template
3. Update `docs/5-integrations/INDEX.md`:
   ```markdown
   ### [Web API Integration](./web-api-integration.md)
   RESTful API integration pattern for third-party services.
   ```
4. Add cross-references from related docs

## References

This maintenance guide itself serves as an example of the documentation structure and style it describes. All DevBoard documentation follows these patterns for consistency and maintainability.

**Last Updated**: 2024 (update when making significant changes to this guide)

## See Also

- [Documentation Home](./INDEX.md): Root documentation index
- [Contributing](./6-development/contributing.md): Development workflow
- [Architecture Overview](./3-architecture/INDEX.md): Technical documentation structure
