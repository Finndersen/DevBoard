"""GitHub API endpoints for PR status across all codebases."""

import asyncio

import logfire
from fastapi import APIRouter, Depends, HTTPException

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
from devboard.integrations.github import GitHubIntegration, GitHubRepository
from devboard.services.integration_service import IntegrationService

router = APIRouter()


@router.get("/open-prs", response_model=OpenPRsResponse)
async def get_open_prs(
    codebase_repo: CodebaseRepository = Depends(get_codebase_repository),
    task_repo: TaskRepository = Depends(get_task_repository),
    integration_service: IntegrationService = Depends(get_integration_service),
) -> OpenPRsResponse:
    """Get all open PRs across all GitHub-connected codebases."""
    codebases = codebase_repo.get_all()
    github_codebases = [cb for cb in codebases if cb.repository_url]

    if not github_codebases:
        return OpenPRsResponse(prs=[], errors=[])

    # Get GitHub integration instance
    try:
        github = integration_service.get_integration_instance(GitHubIntegration)
    except IntegrationConfigurationError as e:
        return OpenPRsResponse(prs=[], errors=[str(e)])

    # Fetch open PRs from all repos in parallel
    async def fetch_prs_for_codebase(
        cb_id: int, cb_name: str, repo_url: str
    ) -> tuple[int, str, list[tuple[int, str, str, str | None]], str | None]:
        try:
            github_repo: GitHubRepository = await github.get_repository_from_url(repo_url)
            pulls = await github_repo.list_open_pulls()
            pr_data: list[tuple[int, str, str, str | None]] = [
                (pr.number, pr.title, pr.html_url, pr.mergeable_state) for pr in pulls
            ]
            return cb_id, github_repo.full_name, pr_data, None
        except Exception as e:
            logfire.error(f"Error fetching PRs for codebase {cb_name}: {e}")
            return cb_id, cb_name, [], str(e)

    results = await asyncio.gather(
        *[
            fetch_prs_for_codebase(cb.id, cb.name, cb.repository_url)  # type: ignore[arg-type]
            for cb in github_codebases
        ],
    )

    # Build task lookup
    codebase_ids = [cb.id for cb in github_codebases]
    tasks_with_prs = task_repo.get_tasks_with_open_prs(codebase_ids)
    task_lookup: dict[tuple[int, int], tuple[int, str]] = {
        (t.codebase_id, t.github_pr_number): (t.id, t.title)  # type: ignore[index]
        for t in tasks_with_prs
    }

    prs: list[OpenPRItem] = []
    errors: list[str] = []

    for result in results:
        if isinstance(result, Exception):
            errors.append(str(result))
            continue

        cb_id, repo_full_name, pr_data, error = result
        if error:
            errors.append(f"{repo_full_name}: {error}")

        for pr_number, title, pr_url, mergeable_state in pr_data:
            task_info = task_lookup.get((cb_id, pr_number))
            prs.append(
                OpenPRItem(
                    pr_number=pr_number,
                    title=title,
                    repo_full_name=repo_full_name,
                    codebase_id=cb_id,
                    pr_url=pr_url,
                    mergeable_state=mergeable_state,
                    task_id=task_info[0] if task_info else None,
                    task_title=task_info[1] if task_info else None,
                )
            )

    return OpenPRsResponse(prs=prs, errors=errors)


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
