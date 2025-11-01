# Document Collaboration

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > Document Collaboration

**Purpose**: Structured document editing with AI through approval workflows, conflict detection, template-based schemas

## Document Types

**Task Specification**: Objective, Context & Background, Requirements, Acceptance Criteria, Resources & References, Constraints & Assumptions

**Implementation Plan**: Summary, Technical Analysis, Implementation Steps, Testing Strategy, Definition of Done

**Project Specification**: Overview, Goals, Current Status, Resources

**Architecture Document**: Overview, Component Architecture, Technology Stack, Development Patterns, Deployment & Operations

## Editing Patterns

**Find-and-Replace**: Agents propose specific text replacements (atomic, reversible, clear preview)

**Full Replacement**: Set entire document (for major restructuring)

**Approval Flow**:
1. Agent proposes tool call
2. UI displays diff view (additions/deletions, side-by-side/unified)
3. User approves/denies/modifies
4. Apply atomically
5. Agent continues

## Document Tools

**edit_* Tools**: Find-and-replace
- Available: edit_task_specification, edit_implementation_plan, edit_project_specification
- Args: `edits` (list of old_string/new_string), `reasoning`
- Fails if old_string not found or not unique

**set_*_content Tools**: Full replacement
- Available: set_task_specification_content, set_implementation_plan_content
- Args: `content`, `reasoning`
- Use cases: Initial creation, major restructuring, template application

## Conflict Detection

**Mechanism**: Content hashing
1. Document read returns content + content_hash
2. Edit includes original_hash
3. Verify current hash matches original_hash
4. Reject if mismatch (concurrent modification)
5. Force refresh and re-apply

**Benefits**: Prevents lost updates, clear errors, no silent overwriting

## Lifecycle

**Creation**: Entity created → template-based document → structure provided → content filled

**Evolution**: Question → agent proposes edits → review → approve → apply → iterate

**Versioning**: Content hash changes per edit, edit history in conversation, Git for architecture docs

## Collaborative Patterns

**Iterative Refinement**: Initial draft → feedback → agent refines → repeat

**Question-Driven**: Ask questions → agent proposes additions → refine → approve

**Template Customization**: Start with standard → remove unnecessary → add specific → reorder

## Role Integration

**ProjectQARole**: Can edit project specifications

**TaskSpecificationRole**: Can edit task specifications

**TaskPlanningRole**: Can edit implementation plans

**TaskImplementationRole**: Read-only (no document editing)

## Use Cases

**Develop Task Spec**: Create task (Designing) → converse with TaskSpecificationRole → agent asks questions → proposes sections → user reviews → iterate

**Create Plan**: Move to Planning → converse with TaskPlanningRole → describe approach → agent analyzes codebase → proposes plan → refine

**Update Project Spec**: Open project → ask ProjectQARole to update → agent proposes changes → review diff → approve

**Architecture Docs**: Register codebase → request generation → review → request improvements → agent proposes edits → approve