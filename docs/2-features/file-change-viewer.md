# File Change Viewer

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > File Change Viewer

## Overview

The **File Change Viewer** provides real-time visibility into uncommitted code changes made during task implementation. Integrated directly into the task detail view, it displays git diffs with syntax highlighting, allowing developers to review implementation progress without leaving the DevBoard interface.

## Purpose

Track and review file modifications made by implementation agents:

- **Progress Monitoring**: See what files have been modified in real-time
- **Code Review**: Review changes with syntax highlighting before committing
- **Quality Assurance**: Catch issues early by reviewing changes as they happen
- **Context Awareness**: Understand implementation progress alongside task specification and plan

## How It Works

### Display Location

The File Changes tab appears in the task detail view's document panel:

- **Tab Position**: Third tab after "Task Specification" and "Implementation Plan"
- **Visibility**: Only shown when task status is `IMPLEMENTING` or `PR_OPEN`
- **Requirement**: Task must have an associated codebase (`codebase_id` not null)

### Data Source

Changes are fetched from the task's associated codebase:

1. Backend executes `git diff HEAD` in the codebase directory
2. Raw diff output is parsed into structured per-file data
3. Statistics calculated (additions/deletions per file and totals)
4. Response includes timestamp for freshness tracking

### Performance Optimization

**Lazy Rendering**: Files collapsed by default for instant loading:

- Initial view shows only file headers with stats
- Click to expand individual files
- Diff parsing and syntax highlighting only occur when expanded
- Handles large changesets (100+ files) without performance degradation

## User Interface

### File List Header

Top-level statistics and controls:

```
5 files changed  +156 -42
Last updated: 2 minutes ago  [Refresh]
```

- **File Count**: Total number of modified files
- **Total Changes**: Aggregate additions and deletions
- **Timestamp**: Relative time since last refresh
- **Refresh Button**: Manually fetch latest changes

### File Headers (Collapsed)

Each file displays summary information:

```
▶ backend/devboard/api/routers/tasks.py  +45 -8
```

- **Chevron Icon**: Indicates collapsed state (▶) or expanded (▼)
- **File Path**: Full relative path from repository root
- **Statistics**: Green additions (+) and red deletions (-)
- **Clickable**: Click anywhere on header to expand/collapse

### Expanded Diff View

When expanded, shows full syntax-highlighted diff:

```
▼ backend/devboard/api/routers/tasks.py  +45 -8
┌──────┬──────┬────────────────────────────────────┐
│  old │  new │ content                            │
├──────┼──────┼────────────────────────────────────┤
│      │      │ @@ -270,6 +270,51 @@            │  (hunk header)
│  270 │  270 │ async def get_task_diff(          │  (context)
│  271 │  271 │     task_id: int,                 │  (context)
│      │  272 │     codebase_repo: Codebase...    │  (added - green)
│  272 │      │     old_param: str,               │  (removed - red)
└──────┴──────┴────────────────────────────────────┘
```

**Features**:
- **Line Numbers**: Shows both old and new line numbers
- **Syntax Highlighting**: Language-specific color coding (30+ languages)
- **Diff Colors**: Green background for additions, red for deletions
- **Horizontal Scroll**: Single scrollbar for entire diff, sticky line numbers
- **Whitespace Preserved**: Indentation and formatting maintained
- **Inline Comments**: Add review comments on any line (see Inline Review Comments section)

### Empty State

When no uncommitted changes exist:

```
[Document Icon]
No file changes yet
When files are modified, they will appear here

[Refresh]
```

Friendly message indicating no changes currently present.

## Supported Languages

Automatic language detection from file extensions:

**Programming Languages**: JavaScript, TypeScript, Python, Go, Rust, Java, C/C++, C#, PHP, Ruby, Swift, Kotlin, Scala

**Web Technologies**: HTML, CSS, SCSS, SASS, LESS, JSON, XML, YAML

**Shell & Config**: Bash, SQL, Markdown, Dockerfile, GraphQL

Falls back to plain text for unknown extensions.

## Technical Implementation

### Backend API

**Endpoint**: `GET /api/tasks/{task_id}/diff`

**Response Schema**:
```json
{
  "files": [
    {
      "file_path": "backend/api/routers/tasks.py",
      "diff_content": "diff --git a/... (full diff)",
      "additions": 45,
      "deletions": 8
    }
  ],
  "total_additions": 156,
  "total_deletions": 42,
  "generated_at": "2024-01-15T10:30:00Z"
}
```

**Error Handling**:
- `400 Bad Request`: Task has no associated codebase
- `404 Not Found`: Codebase not found or path doesn't exist
- `500 Server Error`: Git command failed or repository invalid

### Frontend Components

**GitDiffViewer** (`frontend/src/components/documents/GitDiffViewer.tsx`):
- Renders single file diff with syntax highlighting
- Manages expand/collapse state
- Parses git diff format and tracks line numbers
- Detects dark mode and switches themes accordingly
- Renders inline comment buttons and forms

**AllFilesDiffViewer** (`frontend/src/components/documents/AllFilesDiffViewer.tsx`):
- Container for multiple file diffs
- Manages refresh state and timestamp
- Displays aggregate statistics
- Handles empty state
- Wraps content with DiffReviewProvider when `onSubmitComments` callback is provided

**DiffReviewContext** (`frontend/src/contexts/DiffReviewContext.tsx`):
- Manages pending review comments state
- Accepts `onSubmitComments` callback for submitting formatted comments
- Formats comments with code context (file path, line numbers, surrounding code)

**DiffLineCommentButton** (`frontend/src/components/documents/DiffLineCommentButton.tsx`):
- "+" button that appears on hover after line numbers (GitHub-style placement)
- Shows chat bubble indicator when line has pending comment

**DiffLineCommentForm** (`frontend/src/components/documents/DiffLineCommentForm.tsx`):
- Inline textarea form for writing comments
- Auto-tracks comment in batch as user types
- Send button submits immediately, Cancel removes comment
- Keyboard shortcuts: Ctrl+Enter (send), Escape (cancel)

**SubmitAllCommentsButton** (`frontend/src/components/documents/SubmitAllCommentsButton.tsx`):
- Batch submit button for multiple pending comments
- Shows comment count and clear all option

**PRInlineCommentThread** (`frontend/src/components/documents/PRInlineCommentThread.tsx`):
- Renders a GitHub PR review comment thread inline in the diff at the corresponding line
- Amber/orange styling to distinguish from internal developer comments (blue)
- Shows original comment and replies (read-only)
- "Send to agent" button formats comment context and sends to the implementation agent

**PRGeneralComments** (`frontend/src/components/documents/PRGeneralComments.tsx`):
- Renders review-level comments and standalone comment threads at the bottom of the File Changes tab
- Shown for `pr_open` tasks when PR feedback is available
- Same "Send to agent" functionality as inline PR comments

**Integration** (`frontend/src/views/TaskDetail.tsx`):
- Adds "Changes" tab to task detail view
- Fetches diff data when tab first opened
- Provides manual refresh capability
- Provides `onSubmitComments` callback that sends review comments to the task's conversation

### Syntax Highlighting

Uses `react-syntax-highlighter` with Prism mode:

- **Lightweight**: ~45KB per language (vs ~200KB for Highlight.js)
- **Themes**: `oneDark` (dark mode) and `oneLight` (light mode)
- **Interactive**: Each line is a React component (ready for future comment features)
- **Performance**: Rendered only when file expanded

## Use Cases

### Implementation Progress Tracking

Monitor what the implementation agent has modified:

1. Open task in `IMPLEMENTING` state
2. Click "File Changes" tab
3. See list of all modified files with statistics
4. Expand specific files to review detailed changes
5. Refresh periodically to see latest modifications

### Pre-Commit Review

Review changes before committing to version control:

1. Implementation complete, ready to commit
2. Open File Changes tab
3. Review each modified file for quality and correctness
4. Identify any unwanted changes or issues
5. Request agent fixes if needed
6. Commit once satisfied with all changes

### Understanding Implementation Approach

Understand how the agent approached the task:

1. Read implementation plan to understand strategy
2. Switch to File Changes tab
3. See which files were modified and in what order
4. Expand files to see specific code changes
5. Correlate changes with plan steps

### Debugging Implementation Issues

Identify problems in agent-generated code:

1. Tests failing or unexpected behavior
2. Open File Changes tab to see all modifications
3. Expand relevant files to inspect changes
4. Identify problematic code sections
5. Provide feedback to agent for corrections

## Workflow Integration

The File Change Viewer fits into the task implementation workflow:

```
1. Planning Phase
   ├─ Review implementation plan
   └─ Understand approach

2. Implementation Phase
   ├─ Agent makes code changes
   ├─ Monitor progress via File Changes tab
   ├─ Review changes periodically
   └─ Provide feedback/corrections

3. Review Phase
   ├─ Final review of all changes
   ├─ Verify against requirements
   └─ Prepare for commit

4. Completion
   ├─ Commit changes to version control
   └─ Mark task complete
```

## Best Practices

### Regular Monitoring

- Check File Changes tab periodically during implementation
- Catch issues early before they accumulate
- Refresh to see latest changes

### Comprehensive Review

- Expand and review each modified file before committing
- Verify changes align with implementation plan
- Check for unintended modifications

### Combined Context

- Use File Changes alongside Task Specification and Implementation Plan
- Ensure changes implement the specified requirements
- Verify implementation follows the planned approach

### Refresh Frequently

- Click Refresh before making commit decisions
- Ensure you're viewing the latest changes
- Use timestamp to verify freshness

## Inline Review Comments

During task implementation, developers can add inline review comments directly on diff lines. Comments are sent to the implementation agent with full context.

### Adding a Comment

1. **Hover** over any diff line to reveal the "+" button (appears after line numbers)
2. **Click** the button to open the inline comment form
3. **Type** your feedback - the comment is automatically tracked as you type
4. Choose to:
   - **Send**: Submit this comment immediately to the agent
   - **Cancel**: Remove the comment entirely

### Comment Format

Comments sent to the agent include:
- **File Path**: Full path to the file being reviewed
- **Line Number**: The specific line being commented on (marked with `>>`)
- **Code Context**: 2 lines above and below the commented line
- **Comment Text**: Your review feedback

Example message format:
```markdown
**Review comment** on `src/components/Button.tsx` at line 42:

\`\`\`typescript
     40 │ const Button = ({ onClick }: ButtonProps) => {
     41 │   const handleClick = useCallback(() => {
>>   42 │     onClick?.(event)
     43 │   }, [onClick])
     44 │
\`\`\`

Consider adding error handling here for edge cases.
```

### Batch Submission

When reviewing multiple locations:
- Add comments to multiple lines across files (comments are tracked as you type)
- A "Submit X Comments" button appears in the header
- Submit all comments as a single batched message
- Use "Clear All" to discard all pending comments
- Lines with pending comments show a chat bubble indicator

### Keyboard Shortcuts

- **Ctrl/Cmd + Enter**: Send comment immediately
- **Escape**: Cancel and remove comment

## Limitations

**Current Scope**:
- Shows all uncommitted changes (doesn't distinguish agent vs manual edits)
- Read-only view (cannot edit or revert changes directly)
- Requires git repository (won't work for non-git codebases)

**Future Enhancements**:
- Stage/unstage individual files or hunks
- View commit history for the task
- Filter changes by agent vs manual
- Compare against specific commits or branches

## Related Features

- [Task Management](./task-management.md): Overall task workflow and lifecycle
- [Codebase Integration](../5-integrations/codebase-integration.md): How codebases connect to tasks
- [Document Collaboration](./document-collaboration.md): Specification and plan document editing
