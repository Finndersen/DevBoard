"""GitHub integration for accessing PRs, commits, issues, and branches."""

import asyncio
import re
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Literal, cast

import httpx
import logfire
from github import (
    BadCredentialsException,
    Github,
    GithubException,
    RateLimitExceededException,
    UnknownObjectException,
)
from github.Auth import Token
from github.Branch import Branch
from github.Commit import Commit
from github.CommitCombinedStatus import CommitCombinedStatus
from github.Issue import Issue
from github.PullRequest import PullRequest as GithubPullRequest
from github.PullRequestComment import PullRequestComment
from github.PullRequestReview import PullRequestReview
from github.Repository import Repository

from devboard.config.integration_configs import GitHubIntegrationConfig
from devboard.db.models.codebase import MergeMethod

from .base import (
    AuthenticationError,
    BaseIntegration,
    IntegrationConfigurationError,
    IntegrationConnectionResult,
    IntegrationError,
    RateLimitError,
    ResourceNotFoundError,
)

# Dedicated thread pool for GitHub API calls to prevent thread pool starvation.
# PyGithub calls can hang on 404 redirects/network issues, and if they share FastAPI's
# default executor, they block all sync operations (including DB queries) for other endpoints.
_github_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="github-api")

PRState = Literal["open", "closed"]
MergeableState = Literal["clean", "dirty", "blocked", "behind", "unstable", "unknown", "has_hooks", "queued"]
CIState = Literal["success", "pending", "failure", "error"]


async def _github_api_call[T](method: Callable[..., T], *args: Any, label: str | None = None, **kwargs: Any) -> T:
    """Execute a synchronous PyGithub API call asynchronously in a thread pool.

    Wraps sync PyGithub methods to run in a thread pool executor, enabling proper
    async behavior and consistent error handling across all GitHub API calls.
    """
    call_label = label or getattr(method, "__name__", "<unknown>")

    def _call() -> T:
        return method(*args, **kwargs)

    try:
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(_github_executor, _call),
            timeout=30.0,
        )
    except TimeoutError:
        raise IntegrationError(f"GitHub API call timed out: {call_label}") from None
    except BadCredentialsException as e:
        raise AuthenticationError(f"GitHub authentication failed: {e}") from e
    except RateLimitExceededException as e:
        raise RateLimitError(f"GitHub rate limit exceeded: {e}") from e
    except UnknownObjectException as e:
        raise ResourceNotFoundError(f"Resource not found: {e}") from e
    except GithubException as e:
        logfire.error(f"GitHub API error in {call_label}: {e}")
        raise IntegrationError(f"GitHub error: {e}") from e


@dataclass
class PullRequestMergeResult:
    """Result of merging a pull request."""

    merged: bool
    sha: str | None
    message: str


@dataclass
class CICheck:
    """Individual CI status check."""

    context: str
    state: CIState
    description: str | None


@dataclass
class PRStatus:
    """Comprehensive PR status including CI checks."""

    pr_number: int
    state: PRState
    merged: bool
    mergeable: bool | None
    mergeable_state: MergeableState | None
    ci_status: CIState | None
    ci_checks: list[CICheck]


@dataclass
class ReviewComment:
    """A single review comment with metadata."""

    id: int
    author: str
    body: str
    path: str
    line: int | None
    created_at: datetime | None
    diff_hunk: str | None
    in_reply_to_id: int | None


@dataclass
class CommentThread:
    """A thread of comments starting with an original comment and its replies."""

    original: ReviewComment
    replies: list[ReviewComment]


@dataclass
class ReviewWithComments:
    """A review with its associated comment threads."""

    id: int
    author: str
    state: str
    body: str
    submitted_at: datetime | None
    comment_threads: list[CommentThread]


@dataclass
class PRFeedback:
    """Complete PR feedback including reviews with comments and standalone comment threads."""

    reviews: list[ReviewWithComments]
    standalone_threads: list[CommentThread]


@dataclass
class PullRequest:
    """A pull request fetched via GitHub GraphQL."""

    number: int
    title: str
    html_url: str
    mergeable_state: str | None
    repo_full_name: str
    updated_at: datetime
    review_decision: str | None
    ci_status: str | None
    comment_count: int
    state: str = "OPEN"
    ci_checks: list[CICheck] = field(default_factory=list)


class GitHubPR:
    """Wrapper around PyGithub PullRequest with enhanced methods."""

    def __init__(self, pr: GithubPullRequest, repo: "GitHubRepository"):
        """Initialize with a PyGithub PullRequest object and its repository.

        Args:
            pr: PyGithub PullRequest instance
            repo: GitHubRepository instance this PR belongs to
        """
        self._pr = pr
        self._repo = repo

    @property
    def pr(self) -> GithubPullRequest:
        """The underlying PyGithub PullRequest object."""
        return self._pr

    @property
    def repo(self) -> "GitHubRepository":
        """The repository this PR belongs to."""
        return self._repo

    @property
    def number(self) -> int:
        """The pull request number."""
        return self._pr.number

    async def get_comments(self) -> list[PullRequestComment]:
        """Get inline review comments for the pull request."""
        return await _github_api_call(lambda: list(self._pr.get_review_comments()), label="get_review_comments")

    async def get_reviews(self) -> list[PullRequestReview]:
        """Get reviews for the pull request.

        Returns reviews with state (APPROVED, CHANGES_REQUESTED, COMMENTED, etc.),
        reviewer info, and review body.
        """
        return await _github_api_call(lambda: list(self._pr.get_reviews()), label="get_reviews")

    async def get_feedback(self) -> PRFeedback:
        """Get comprehensive PR feedback including reviews with associated comment threads.

        Fetches both reviews and comments, then:
        1. Associates comments with their parent reviews using pull_request_review_id
        2. Groups reply comments into threads using in_reply_to_id
        3. Separates standalone comments (not associated with any review)

        Returns:
            PRFeedback containing reviews with their comment threads and standalone threads
        """
        raw_reviews = await _github_api_call(lambda: list(self._pr.get_reviews()), label="get_reviews")
        raw_comments = await _github_api_call(lambda: list(self._pr.get_review_comments()), label="get_review_comments")

        # Convert raw comments to ReviewComment dataclass
        def to_review_comment(c: PullRequestComment) -> ReviewComment:
            return ReviewComment(
                id=c.id,
                author=c.user.login if c.user else "Unknown",
                body=c.body or "",
                path=c.path or "unknown",
                line=c.line or c.original_line,
                created_at=c.created_at,
                diff_hunk=c.diff_hunk,
                in_reply_to_id=c.in_reply_to_id,
            )

        comments = [to_review_comment(c) for c in raw_comments]

        # Group comments by review id
        comments_by_review: dict[int | None, list[ReviewComment]] = {}
        for comment, raw_comment in zip(comments, raw_comments, strict=True):
            review_id = raw_comment.pull_request_review_id
            if review_id not in comments_by_review:
                comments_by_review[review_id] = []
            comments_by_review[review_id].append(comment)

        # Build threads from comments
        def build_threads(comment_list: list[ReviewComment]) -> list[CommentThread]:
            # Find root comments (not replies)
            root_comments = [c for c in comment_list if c.in_reply_to_id is None]

            # Build reply lookup
            replies_by_parent: dict[int, list[ReviewComment]] = {}
            for c in comment_list:
                if c.in_reply_to_id is not None:
                    if c.in_reply_to_id not in replies_by_parent:
                        replies_by_parent[c.in_reply_to_id] = []
                    replies_by_parent[c.in_reply_to_id].append(c)

            threads: list[CommentThread] = []
            for root in root_comments:
                # Collect all replies (including nested) - flatten into single list
                all_replies: list[ReviewComment] = []
                to_process = [root.id]
                processed: set[int] = set()

                while to_process:
                    parent_id = to_process.pop(0)
                    if parent_id in processed:
                        continue
                    processed.add(parent_id)

                    if parent_id in replies_by_parent:
                        for reply in replies_by_parent[parent_id]:
                            all_replies.append(reply)
                            to_process.append(reply.id)

                # Sort replies by created_at
                all_replies.sort(key=lambda r: r.created_at or datetime.min)
                threads.append(CommentThread(original=root, replies=all_replies))

            return threads

        # Build reviews with comment threads
        reviews_with_comments: list[ReviewWithComments] = []
        for review in raw_reviews:
            review_comments = comments_by_review.get(review.id, [])
            threads = build_threads(review_comments)

            reviews_with_comments.append(
                ReviewWithComments(
                    id=review.id,
                    author=review.user.login if review.user else "Unknown",
                    state=review.state or "UNKNOWN",
                    body=review.body or "",
                    submitted_at=review.submitted_at,
                    comment_threads=threads,
                )
            )

        # Build standalone threads (comments not associated with any review)
        standalone_comments = comments_by_review.get(None, [])
        standalone_threads = build_threads(standalone_comments)

        return PRFeedback(
            reviews=reviews_with_comments,
            standalone_threads=standalone_threads,
        )

    async def get_status(self) -> PRStatus:
        """Get comprehensive PR status including CI checks.

        Combines PR metadata (state, mergeable) with CI status checks.
        Uses the stored repository reference to fetch CI status.
        """
        ci_status: CIState | None = None
        ci_checks: list[CICheck] = []

        head_sha = self._pr.head.sha if self._pr.head else None
        if head_sha:
            try:
                combined = await self._repo.get_combined_status(head_sha)
                ci_status = cast(CIState, combined.state)
                ci_checks = [
                    CICheck(
                        context=s.context,
                        state=cast(CIState, s.state),
                        description=s.description,
                    )
                    for s in combined.statuses
                ]
            except IntegrationError:
                pass  # CI status unavailable

        return PRStatus(
            pr_number=self._pr.number,
            state=cast(PRState, self._pr.state),
            merged=self._pr.merged,
            mergeable=self._pr.mergeable,
            mergeable_state=cast(MergeableState | None, self._pr.mergeable_state),
            ci_status=ci_status,
            ci_checks=ci_checks,
        )

    async def merge(
        self,
        merge_method: MergeMethod = MergeMethod.SQUASH,
        commit_title: str | None = None,
        commit_message: str | None = None,
    ) -> PullRequestMergeResult:
        """Merge the pull request.

        Args:
            merge_method: How to merge - squash, rebase, or merge_commit (default: squash)
            commit_title: Optional custom commit title
            commit_message: Optional custom commit message

        Returns:
            Merge result including merge commit SHA

        Raises:
            AuthenticationError: If GitHub authentication fails
            RateLimitError: If GitHub rate limit exceeded
            IntegrationError: For other GitHub errors (including merge conflicts)
        """
        # Map MergeMethod to GitHub API merge_method parameter
        github_merge_method_map = {
            MergeMethod.SQUASH: "squash",
            MergeMethod.REBASE: "rebase",
            MergeMethod.MERGE_COMMIT: "merge",
        }
        github_merge_method = github_merge_method_map[merge_method]

        # Build merge parameters
        merge_params: dict[str, Any] = {"merge_method": github_merge_method}
        if commit_title:
            merge_params["commit_title"] = commit_title
        if commit_message:
            merge_params["commit_message"] = commit_message

        result = await _github_api_call(self._pr.merge, **merge_params)
        return PullRequestMergeResult(
            merged=result.merged,
            sha=result.sha,
            message=result.message,
        )


class GitHubRepository:
    """Wrapper around PyGithub Repository with async methods.

    Provides repository-scoped operations without requiring owner/repo
    parameters on each call. Encapsulates error handling for GitHub API calls.
    """

    def __init__(self, repo: Repository):
        """Initialize with a PyGithub Repository object.

        Args:
            repo: PyGithub Repository instance
        """
        self._repo = repo

    @property
    def owner(self) -> str:
        """Repository owner login name."""
        return self._repo.owner.login

    @property
    def name(self) -> str:
        """Repository name."""
        return self._repo.name

    @property
    def full_name(self) -> str:
        """Full repository name (owner/repo)."""
        return self._repo.full_name

    @property
    def description(self) -> str | None:
        """Repository description."""
        return self._repo.description

    @property
    def language(self) -> str | None:
        """Primary programming language of the repository."""
        return self._repo.language

    async def get_pull_request(self, pr_number: int) -> GitHubPR:
        """Fetch a pull request and return a wrapped GitHubPR instance.

        Args:
            pr_number: Pull request number

        Returns:
            GitHubPR wrapper with PR-specific methods and reference to this repository

        Raises:
            ResourceNotFoundError: If PR not found
            AuthenticationError: If GitHub auth fails
            RateLimitError: If rate limited
            IntegrationError: For other GitHub errors
        """
        pr_obj = await _github_api_call(self._repo.get_pull, pr_number)
        return GitHubPR(pr_obj, self)

    async def get_commit(self, sha: str) -> Commit:
        """Get details of a specific commit."""
        return await _github_api_call(self._repo.get_commit, sha)

    async def get_issue(self, issue_number: int) -> Issue:
        """Get details of a specific issue."""
        return await _github_api_call(self._repo.get_issue, issue_number)

    async def list_branches(self) -> list[Branch]:
        """List branches in the repository."""
        return await _github_api_call(lambda: list(self._repo.get_branches()), label="list_branches")

    async def list_open_pulls(self) -> list[GithubPullRequest]:
        """List all open pull requests for this repository."""
        return await _github_api_call(lambda: list(self._repo.get_pulls(state="open")), label="list_open_pulls")

    async def find_pull_request_for_branch(self, head_branch: str) -> GithubPullRequest | None:
        """Find an existing open PR for the given head branch.

        Args:
            head_branch: The head branch name (without owner prefix)

        Returns:
            The PullRequest if found, None otherwise
        """
        # PyGithub expects head in format "owner:branch" for cross-repo PRs
        head = f"{self._repo.owner.login}:{head_branch}"

        def _find_pr() -> GithubPullRequest | None:
            for pr in self._repo.get_pulls(state="open", head=head):
                return pr
            return None

        return await _github_api_call(_find_pr)

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> GithubPullRequest:
        """Create a new pull request."""
        return await _github_api_call(self._repo.create_pull, title=title, body=body, head=head, base=base)

    async def get_combined_status(self, ref: str) -> CommitCombinedStatus:
        """Get combined status checks for a ref (branch or commit SHA).

        Returns the combined state (success, pending, failure) and individual check statuses.
        """

        def _get_combined_status() -> CommitCombinedStatus:
            commit = self._repo.get_commit(ref)
            return commit.get_combined_status()

        return await _github_api_call(_get_combined_status)


PR_CACHE_MAX_AGE = 60.0  # seconds


@dataclass
class PRCacheEntry:
    """Cache entry for a single PR status."""

    data: "PullRequest"
    fetched_at: float = field(default_factory=time.time)


def _extract_ci_status(node: dict[str, Any]) -> str | None:
    """Extract CI rollup status from a GraphQL PR node."""
    commits = node.get("commits", {}).get("nodes", [])
    if not commits:
        return None
    rollup = commits[0].get("commit", {}).get("statusCheckRollup")
    if not rollup:
        return None
    return rollup.get("state")


def _check_run_to_ci_state(check_run: dict[str, Any]) -> CIState:
    """Map a GraphQL CheckRun conclusion/status to CIState."""
    conclusion = check_run.get("conclusion")
    if conclusion is None:
        return "pending"
    match conclusion:
        case "SUCCESS" | "NEUTRAL" | "SKIPPED":
            return "success"
        case "FAILURE" | "TIMED_OUT" | "ACTION_REQUIRED" | "STARTUP_FAILURE":
            return "failure"
        case _:  # CANCELLED, STALE
            return "error"


def _extract_ci_checks(node: dict[str, Any]) -> list[CICheck]:
    """Extract individual CI checks from a GraphQL PR node's statusCheckRollup contexts."""
    commits = node.get("commits", {}).get("nodes", [])
    if not commits:
        return []
    rollup = commits[0].get("commit", {}).get("statusCheckRollup")
    if not rollup:
        return []

    checks: list[CICheck] = []
    for context in rollup.get("contexts", {}).get("nodes", []):
        if context is None:
            continue
        typename = context.get("__typename")
        if typename == "StatusContext":
            checks.append(
                CICheck(
                    context=context["context"],
                    state=cast(CIState, context["state"].lower()),
                    description=context.get("description"),
                )
            )
        elif typename == "CheckRun":
            checks.append(
                CICheck(
                    context=context["name"],
                    state=_check_run_to_ci_state(context),
                    description=context.get("title"),
                )
            )
    return checks


def _resolve_api_token(config: "GitHubIntegrationConfig") -> str:
    """Return the configured token, or fall back to `gh auth token` if none is set."""
    if config.api_token:
        return config.api_token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise IntegrationConfigurationError(
                "No GitHub token configured and `gh auth token` failed. "
                "Either configure a token or run `gh auth login`."
            )
        return result.stdout.strip()
    except FileNotFoundError as e:
        raise IntegrationConfigurationError(
            "No GitHub token configured and `gh` CLI is not installed. "
            "Either configure a token or install the GitHub CLI."
        ) from e


class GitHubIntegration(BaseIntegration):
    """Integration for GitHub API access."""

    integration_type = "github"
    configuration_schema = GitHubIntegrationConfig

    # Class-level PR status cache (persists across per-request instances)
    _pr_cache: ClassVar[dict[str, PRCacheEntry]] = {}
    _last_batch_fetch_at: ClassVar[float] = 0.0

    @staticmethod
    def _cache_key(repo_full_name: str, pr_number: int) -> str:
        """Build cache key from repo full name and PR number."""
        return f"{repo_full_name}:{pr_number}"

    @staticmethod
    def parse_repo_url(url: str) -> tuple[str, str]:
        """Parse owner and repo from a GitHub repository URL.

        Supports formats:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git

        Args:
            url: GitHub repository URL

        Returns:
            Tuple of (owner, repo)

        Raises:
            ValueError: If URL format is not recognized
        """
        # HTTPS format: https://github.com/owner/repo(.git)?
        https_match = re.match(r"https://github\.com/([^/]+)/([^/.]+)(?:\.git)?", url)
        if https_match:
            return https_match.group(1), https_match.group(2)

        # SSH format: git@github.com:owner/repo.git
        ssh_match = re.match(r"git@github\.com:([^/]+)/([^/.]+)(?:\.git)?", url)
        if ssh_match:
            return ssh_match.group(1), ssh_match.group(2)

        raise ValueError(f"Unrecognized GitHub repository URL format: {url}")

    def __init__(self, config: GitHubIntegrationConfig):
        """Initialize with GitHub configuration and client."""
        super().__init__(config)
        self._token = _resolve_api_token(config)
        self.client = Github(auth=Token(self._token), base_url=config.base_url)
        logfire.info("Initialized GitHub integration")

    async def test_connection(self) -> IntegrationConnectionResult:
        """Test GitHub API connection."""
        try:
            user = await _github_api_call(self.client.get_user)
            return IntegrationConnectionResult(
                success=True, message=f"Successfully connected to GitHub as {user.login}"
            )
        except AuthenticationError:
            return IntegrationConnectionResult(
                success=False, message="GitHub authentication failed: Invalid credentials"
            )
        except RateLimitError as e:
            return IntegrationConnectionResult(success=False, message=str(e))

    async def get_repository(self, owner: str, repo: str) -> GitHubRepository:
        """Get a repository wrapper for the given owner/repo.

        Args:
            owner: Repository owner (username or organization)
            repo: Repository name

        Returns:
            GitHubRepository wrapper with repository-scoped methods
        """
        repo_obj = await _github_api_call(self.client.get_repo, f"{owner}/{repo}")
        return GitHubRepository(repo_obj)

    async def get_repository_from_url(self, url: str) -> GitHubRepository:
        """Convenience method to get a repository wrapper from a GitHub URL.

        Args:
            url: GitHub repository URL (https or SSH format)

        Returns:
            GitHubRepository wrapper with repository-scoped methods
        """
        owner, repo = self.parse_repo_url(url)
        return await self.get_repository(owner, repo)

    async def _graphql_request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a GitHub GraphQL request and return the response data."""
        config = cast(GitHubIntegrationConfig, self.config)
        base_url = config.base_url.rstrip("/")
        if base_url == "https://api.github.com":
            graphql_url = "https://api.github.com/graphql"
        else:
            graphql_url = base_url.replace("/api/v3", "/api/graphql")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                graphql_url,
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        if "errors" in data:
            # Partial success: data is present but some fields were inaccessible (e.g. FORBIDDEN).
            # Log and continue — callers receive null values for those fields.
            if data.get("data") is not None:
                logfire.warning(f"GitHub GraphQL partial errors (returning data): {data['errors']}")
            else:
                raise IntegrationError(f"GitHub GraphQL error: {data['errors']}")

        return data

    async def get_user_open_pull_requests(
        self, updated_since_days: int = 30, force_refresh: bool = False
    ) -> list[PullRequest]:
        """Fetch all open PRs authored by the authenticated user via GraphQL.

        Returns cached data if a fresh batch has been fetched (< PR_CACHE_MAX_AGE seconds old) unless
        force_refresh is True. Individual PR cache updates are reflected automatically via state filtering.
        """
        now = time.time()
        if (
            not force_refresh
            and GitHubIntegration._last_batch_fetch_at
            and now - GitHubIntegration._last_batch_fetch_at < PR_CACHE_MAX_AGE
        ):
            return [e.data for e in GitHubIntegration._pr_cache.values() if e.data.state == "OPEN"]

        cutoff = (datetime.now(tz=UTC) - timedelta(days=updated_since_days)).strftime("%Y-%m-%d")
        search_query = f"type:pr state:open author:@me draft:false updated:>={cutoff}"
        query = """
        query($q: String!) {
          search(query: $q, type: ISSUE, first: 100) {
            nodes {
              ... on PullRequest {
                number
                title
                url
                updatedAt
                mergeable
                mergeStateStatus
                mergeQueueEntry { id }
                reviewDecision
                totalCommentsCount
                commits(last: 1) {
                  nodes {
                    commit {
                      statusCheckRollup {
                        state
                      }
                    }
                  }
                }
                repository { nameWithOwner }
              }
            }
          }
        }
        """
        data = await self._graphql_request(query, {"q": search_query})
        nodes = data["data"]["search"]["nodes"]
        fetched_at = time.time()
        results = [
            PullRequest(
                number=node["number"],
                title=node["title"],
                html_url=node["url"],
                mergeable_state="QUEUED" if node.get("mergeQueueEntry") else node.get("mergeStateStatus"),
                repo_full_name=node["repository"]["nameWithOwner"],
                updated_at=datetime.fromisoformat(node["updatedAt"]),
                review_decision=node.get("reviewDecision"),
                ci_status=_extract_ci_status(node),
                comment_count=node.get("totalCommentsCount", 0),
            )
            for node in nodes
            if node
        ]
        # Replace per-PR cache entirely with fresh batch data, evicting closed/merged PRs
        GitHubIntegration._pr_cache = {
            self._cache_key(pr.repo_full_name, pr.number): PRCacheEntry(data=pr, fetched_at=fetched_at)
            for pr in results
        }
        GitHubIntegration._last_batch_fetch_at = fetched_at
        return results

    async def get_pull_request_status(
        self, owner: str, repo: str, pr_number: int, force_refresh: bool = False
    ) -> PullRequest:
        """Fetch status of a single PR via GraphQL.

        Returns cached data if fresh (< PR_CACHE_MAX_AGE seconds old) unless force_refresh is True.
        """
        key = self._cache_key(f"{owner}/{repo}", pr_number)
        if not force_refresh:
            entry = GitHubIntegration._pr_cache.get(key)
            if entry and time.time() - entry.fetched_at < PR_CACHE_MAX_AGE:
                return entry.data

        query = """
        query($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            pullRequest(number: $number) {
              number
              title
              url
              updatedAt
              state
              mergeStateStatus
              mergeQueueEntry { id }
              reviewDecision
              totalCommentsCount
              commits(last: 1) {
                nodes {
                  commit {
                    statusCheckRollup {
                      state
                      contexts(last: 100) {
                        nodes {
                          __typename
                          ... on StatusContext {
                            context
                            state
                            description
                          }
                          ... on CheckRun {
                            name
                            conclusion
                            status
                            title
                          }
                        }
                      }
                    }
                  }
                }
              }
              repository { nameWithOwner }
            }
          }
        }
        """
        data = await self._graphql_request(query, {"owner": owner, "name": repo, "number": pr_number})
        repository = data["data"].get("repository")
        if not repository:
            raise IntegrationError(f"Repository {owner}/{repo} not found or inaccessible")
        node = repository.get("pullRequest")
        if not node:
            raise IntegrationError(f"Pull request #{pr_number} not found in {owner}/{repo}")
        result = PullRequest(
            number=node["number"],
            title=node["title"],
            html_url=node["url"],
            state=node["state"],
            mergeable_state="QUEUED" if node.get("mergeQueueEntry") else node.get("mergeStateStatus"),
            repo_full_name=node["repository"]["nameWithOwner"],
            updated_at=datetime.fromisoformat(node["updatedAt"]),
            review_decision=node.get("reviewDecision"),
            ci_status=_extract_ci_status(node),
            comment_count=node.get("totalCommentsCount", 0),
            ci_checks=_extract_ci_checks(node),
        )
        GitHubIntegration._pr_cache[key] = PRCacheEntry(data=result, fetched_at=time.time())
        return result

    async def search_issues(self, query: str, owner: str | None = None, repo: str | None = None) -> list[Issue]:
        """Search issues across GitHub."""
        search_query = query
        if owner and repo:
            search_query += f" repo:{owner}/{repo}"

        return await _github_api_call(lambda: list(self.client.search_issues(search_query)), label="search_issues")
