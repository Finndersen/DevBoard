"""GitHub API endpoints for PR status across all codebases."""

import asyncio

import logfire
from fastapi import APIRouter, Depends, HTTPException, Query

from devboard.api.dependencies.repositories import get_codebase_repository, get_task_repository
from devboard.api.dependencies.services import get_integration_service
from devboard.api.schemas.github import (
    OpenPRItem,
    OpenPRsResponse,
    PRCheckItem,
    PRDetailResponse,
    PRReviewItem,
)
from devboard.db.repositories import CodebaseRepository, TaskRepository
from devboard.integrations.base import IntegrationConfigurationError, IntegrationError
from devboard.integrations.github import GitHubIntegration
from devboard.services.integration_service import IntegrationService

router = APIRouter()


@router.get("/open-prs", response_model=OpenPRsResponse)
async def get_open_prs(
    force_refresh: bool = Query(False),
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    integration_service: IntegrationService = Depends(get_integration_service),
) -> OpenPRsResponse:
    """Get all non-draft open PRs authored by the current user."""
    # Get GitHub integration instance
    try:
        github = integration_service.get_integration_instance(GitHubIntegration)
    except IntegrationConfigurationError as e:
        return OpenPRsResponse(prs=[], errors=[str(e)])

    # Fetch all user's open PRs in a single GraphQL call
    try:
        all_user_prs = await github.get_user_open_pull_requests(force_refresh=force_refresh)
    except Exception as e:
        logfire.error(f"Error fetching user open PRs: {e}")
        return OpenPRsResponse(prs=[], errors=[str(e)])

    # Build repo name → codebase_id lookup from configured codebases
    codebases = codebase_repo.get_all()
    github_codebases = [cb for cb in codebases if cb.repository_url]

    repo_to_codebase: dict[str, int] = {}
    for cb in github_codebases:
        assert cb.repository_url is not None
        owner, repo = GitHubIntegration.parse_repo_url(cb.repository_url)
        repo_to_codebase[f"{owner}/{repo}".lower()] = cb.id

    # Build task lookup for codebases we know about
    codebase_ids = [cb.id for cb in github_codebases]
    task_lookup: dict[tuple[int, int], tuple[int, str]] = {}
    if codebase_ids:
        tasks_with_prs = task_repo.get_tasks_with_open_prs(codebase_ids)
        task_lookup = {
            (t.codebase_id, t.github_pr_number): (t.id, t.title)
            for t in tasks_with_prs
            if t.codebase_id is not None and t.github_pr_number is not None
        }

    # Include all PRs, enriching with codebase/task info when available
    prs: list[OpenPRItem] = []
    for pr in all_user_prs:
        cb_id = repo_to_codebase.get(pr.repo_full_name.lower())
        task_info = task_lookup.get((cb_id, pr.number)) if cb_id is not None else None
        prs.append(
            OpenPRItem(
                pr_number=pr.number,
                title=pr.title,
                repo_full_name=pr.repo_full_name,
                codebase_id=cb_id,
                pr_url=pr.html_url,
                mergeable_state=pr.mergeable_state,
                task_id=task_info[0] if task_info else None,
                task_title=task_info[1] if task_info else None,
                updated_at=pr.updated_at,
                review_decision=pr.review_decision,
                ci_status=pr.ci_status,
                comment_count=pr.comment_count,
            )
        )

    return OpenPRsResponse(prs=prs, errors=[])


@router.get("/prs/{codebase_id}/{pr_number}/detail", response_model=PRDetailResponse)
async def get_pr_detail(
    codebase_id: int,
    pr_number: int,
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    integration_service: IntegrationService = Depends(get_integration_service),
) -> PRDetailResponse:
    """Get detailed PR status including CI checks and reviews."""
    codebase = codebase_repo.get_by_id(codebase_id)
    if not codebase:
        raise HTTPException(status_code=404, detail="Codebase not found")
    if not codebase.repository_url:
        raise HTTPException(status_code=400, detail="Codebase has no repository URL configured")

    try:
        github = integration_service.get_integration_instance(GitHubIntegration)
        github_repo = await github.get_repository_from_url(codebase.repository_url)
        github_pr = await github_repo.get_pull_request(pr_number)
    except IntegrationConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except IntegrationError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    # Fetch status, reviews, and comments in parallel
    status, reviews, comments = await asyncio.gather(
        github_pr.get_status(),
        github_pr.get_reviews(),
        github_pr.get_comments(),
    )

    return PRDetailResponse(
        ci_status=status.ci_status,
        checks=[PRCheckItem(name=c.context, state=c.state, description=c.description) for c in status.ci_checks],
        reviews=[
            PRReviewItem(
                author=r.user.login if r.user else "Unknown",
                state=r.state or "UNKNOWN",
                body=r.body or "",
            )
            for r in reviews
        ],
        review_comment_count=len(comments),
    )
