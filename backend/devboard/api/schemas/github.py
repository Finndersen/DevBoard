"""GitHub-specific API response schemas."""

from pydantic import BaseModel

from devboard.api.schemas.task import GitHubPRStatusResponse


class AssociatedTask(BaseModel):
    task_id: int
    task_title: str
    codebase_id: int


class OpenPRItem(BaseModel):
    pr_status: GitHubPRStatusResponse
    associated_task: AssociatedTask | None


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
