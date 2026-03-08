# GitHub PR Status Bar

**Navigation**: [Documentation Home](../INDEX.md) > [Features](./INDEX.md) > GitHub PR Status Bar

## Overview

The GitHub PR Status Bar provides at-a-glance visibility into all open pull requests across GitHub-connected codebases, displayed in the application header bar.

## Feature Description

A horizontal list of compact PR pills is shown in the top header bar, to the left of the notifications panel. Each pill represents an open GitHub PR and displays:

- **Repository name and PR number** (e.g., `DevBoard #42`)
- **PR title** (truncated for long titles)
- **Status dot** color-coded by `mergeable_state`:
  - Green: `clean` (ready to merge)
  - Yellow/amber: `behind`, `blocked`, `unknown`
  - Red: `dirty`, `unstable` (has conflicts or failing checks)

### Actions

Each PR pill provides:
- **Open in GitHub**: Opens the PR URL in a new browser tab
- **Open Task**: Navigates to the associated DevBoard task (only shown when a task is linked)

### Expanded Detail View

Clicking a PR pill opens a popover showing on-demand detail:
- **CI Checks**: Overall CI status and individual check names with pass/fail/pending indicators
- **Reviews**: List of reviewers with their review state (approved, changes requested, commented)
- **Review comment count**

Only one PR can be expanded at a time.

### Refresh

A manual refresh button re-fetches the PR list. No automatic polling is performed.

## API Endpoints

### `GET /api/github/open-prs`

Returns all open PRs across all GitHub-connected codebases, correlated with DevBoard tasks.

- Queries GitHub for open PRs across all codebases with a `repository_url`
- Matches PRs to DevBoard tasks by `github_pr_number` and `codebase_id`
- Handles per-codebase errors gracefully (partial results returned)
- Does not fetch detailed CI checks (lightweight listing)

### `GET /api/github/prs/{codebase_id}/{pr_number}/detail`

Returns detailed status for a single PR (called on-demand when expanding a PR pill).

- CI check results with individual check names and states
- Review summary with author and review state
- Review comment count

## Architecture

- **Backend**: New router (`api/routers/github.py`) with two endpoints, using existing `GitHubRepository` and `GitHubPR` wrappers
- **Frontend**: `GitHubPRStatusBar` component in `components/github/`, integrated into `AppShell` header bar
- **Data flow**: GitHub API → Backend aggregation → Frontend display with on-demand detail loading
