# GitHub PR Dropdown

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > GitHub PR Dropdown

## Overview

The GitHub PR Dropdown provides at-a-glance visibility into all open pull requests via a compact dropdown button in the application header bar, positioned next to the notifications bell.

## Feature Description

A dropdown trigger button with a PR icon and badge count is displayed in the top header bar. Clicking it reveals a scrollable list of open PRs with inline status indicators.

### Staleness Filtering

Only PRs updated within the last 30 days are shown. Stale PRs (not updated for over 30 days) are automatically filtered out on the backend using GitHub's `updatedAt` field.

### PR List Items

Each PR in the dropdown list displays:

- **Status dot** color-coded by `mergeable_state`:
  - Green: `clean` (ready to merge)
  - Yellow/amber: `behind`, `blocked`, `unknown`
  - Red: `dirty`, `unstable` (has conflicts or failing checks)
- **Repository name and PR number** (e.g., `DevBoard #42`)
- **Relative time** since last update (e.g., `3d ago`)
- **PR title** (truncated for long titles)
- **Inline status indicators** (fetched via GraphQL in a single query):
  - **CI status**: Check mark (passing), cross (failing), or circle (pending)
  - **Review decision**: Badge showing "Approved", "Changes", or "Review needed"
  - **Comment count**: Bubble icon with count (hidden when zero)

### Actions

Each PR list item provides:
- **Open in GitHub**: Opens the PR URL in a new browser tab
- **Open Task**: Navigates to the associated DevBoard task (only shown when a task is linked)

### Badge Count

The trigger button shows a badge with the number of open PRs (hidden when zero).

### Header

The dropdown header shows "Pull Requests ({count})" with a refresh button and error warning icon (when applicable).

### Refresh

A manual refresh button in the dropdown header re-fetches the PR list. No automatic polling is performed.

## API Endpoints

### `GET /api/github/open-prs`

Returns all open PRs across all GitHub-connected codebases, correlated with DevBoard tasks.

- Queries GitHub for open PRs via a single GraphQL call
- Fetches CI rollup status, review decision, and comment count inline via GraphQL
- Filters out PRs not updated in the last 30 days
- Matches PRs to DevBoard tasks by `github_pr_number` and `codebase_id`
- Returns `updated_at`, `ci_status`, `review_decision`, and `comment_count` for each PR
- Handles errors gracefully (partial results returned)

### `GET /api/github/prs/{codebase_id}/{pr_number}/detail`

Returns detailed status for a single PR (available for programmatic use).

- CI check results with individual check names and states
- Review summary with author and review state
- Review comment count

## PR Review Agent (TaskPRReviewRole)

When a task is in `PR_OPEN` state, the **TaskPRReviewRole** agent is available in the Task Detail conversation. This role uses the CLAUDE_CODE engine and provides tools for reading and responding to PR feedback directly from the DevBoard UI.

### Available Tools

- **`get_pr_status`** — Checks the current PR state, CI check results (pass/fail/pending), review decision, and merge readiness. Use this to assess whether a PR is ready to merge before taking action.
- **`get_pr_feedback`** — Fetches all review comments and code-level feedback from GitHub reviewers, including inline comments tied to specific lines of code.
- **`merge_pr_and_finalise`** — Merges the PR on GitHub and transitions the task to `MERGED` state, completing the PR workflow.
- **Codebase tools** — `code_structure_search` and `directory_tree` for exploring the codebase, plus Claude Code's built-in Read, Grep, Glob, Bash, Edit, and Write tools for making changes.

### Workflow

1. Open the task conversation with the task in `PR_OPEN` state
2. Ask the agent to check CI status or summarise reviewer feedback
3. The agent reads the PR comments and proposes or makes code changes
4. Changes are committed and pushed; the agent can rebase if needed
5. Once the PR is approved and CI passes, use `merge_pr_and_finalise` to merge and complete the task

### Notes

- Codebase editing (Edit/Write) is provided by the Claude Code engine, not via explicit tools
- The agent works in the task's checked-out worktree directory
- Commits should be focused and atomic; the agent avoids adding attribution messages

## Architecture

- **Backend**: Router (`api/routers/github.py`) with two endpoints; GraphQL query enriched with CI/review/comment data
- **Frontend**: `GitHubPRDropdown` component in `components/github/`, integrated into `AppShell` header bar
- **Data flow**: GitHub GraphQL API → Backend aggregation + staleness filter → Frontend dropdown with inline status display
