"""GitHub-specific API response schemas."""

from pydantic import BaseModel


class OpenPRItem(BaseModel):
    pr_number: int
    title: str
    repo_full_name: str
    codebase_id: int | None
    pr_url: str
    mergeable_state: str | None
    task_id: int | None
    task_title: str | None


class OpenPRsResponse(BaseModel):
    prs: list[OpenPRItem]
    errors: list[str]


class PRCheckItem(BaseModel):
    name: str
    state: str
    description: str | None


class PRReviewItem(BaseModel):
    author: str
    state: str
    body: str


class PRDetailResponse(BaseModel):
    ci_status: str | None
    checks: list[PRCheckItem]
    reviews: list[PRReviewItem]
    review_comment_count: int
