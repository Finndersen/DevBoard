"""Main FastAPI application."""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from devboard.agents.execution.manager import ConversationExecutionManager
from devboard.agents.execution.registry import get_execution_manager, set_execution_manager
from devboard.agents.language_models import DEFAULT_MODELS
from devboard.api.routers import (
    agents,
    background_agent_runs,
    background_agents,
    claude_code,
    codebases,
    configurations,
    conversations,
    custom_fields,
    documents,
    executions,
    github,
    global_context,
    language_models,
    log_entries,
    mcp_servers,
    oauth,
    projects,
    settings,
    tasks,
    tool_approvals,
    websocket,
    worktrees,
)
from devboard.config.logfire_config import setup_logfire
from devboard.db.database import SessionLocal, engine
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.language_model import LanguageModelRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.services.workspace.pool_manager import WorktreePoolManager

"""Load environment variables from .env files in current directory or home directory."""
load_dotenv(Path.cwd() / ".env", override=False)
load_dotenv(Path.home() / ".env", override=False)

# Prevent subprocesses (e.g. Claude Code CLI) from inheriting the server's VIRTUAL_ENV.
# The running Python interpreter doesn't use VIRTUAL_ENV at runtime (sys.prefix is set at
# interpreter start), so removing it here is safe and avoids uv warnings in child processes.
os.environ.pop("VIRTUAL_ENV", None)


_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 60


async def _event_loop_monitor() -> None:
    while True:
        t = time.monotonic()
        await asyncio.sleep(0.1)
        lag_ms = (time.monotonic() - t - 0.1) * 1000
        if lag_ms > 1000:
            logfire.error(f"Event loop blocked for {lag_ms:.0f}ms")
        elif lag_ms > 200:
            logfire.warn(f"Event loop lag: {lag_ms:.0f}ms")


@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    """Run both lifespans."""
    set_execution_manager(ConversationExecutionManager())
    seed_language_models()
    await cleanup_stale_locks_on_startup()
    # Enable asyncio debug mode to log slow callbacks with their coroutine name/location
    loop = asyncio.get_running_loop()
    loop.set_debug(True)
    loop.slow_callback_duration = 0.05  # warn on anything > 50ms
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    monitor_task = asyncio.create_task(_event_loop_monitor())
    try:
        yield
    finally:
        monitor_task.cancel()
        await _shutdown_active_executions()


async def _shutdown_active_executions() -> None:
    """Wait for active agent executions to finish before shutdown.

    This prevents subprocess orphaning when uvicorn hot-reloads or restarts.
    Executions are not interrupted — they are allowed to complete naturally,
    consistent with how uvicorn handles in-flight HTTP requests.
    """
    active = get_execution_manager().list_active_executions()
    if not active:
        return

    logfire.info(f"Shutdown: waiting for {len(active)} active execution(s) to complete")
    tasks = [e.asyncio_task for e in active]
    _, pending = await asyncio.wait(tasks, timeout=_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS)

    if pending:
        logfire.warning(f"Shutdown: {len(pending)} execution(s) did not finish within timeout, cancelling")
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


def seed_language_models() -> None:
    """Seed the language_models table with default models if it is empty.

    Idempotent — only runs when the table is empty. This ensures that the
    default model catalog is available without requiring manual data entry,
    while allowing user customisation once populated.
    """
    db = SessionLocal()
    try:
        repo = LanguageModelRepository(db)
        if repo.count() == 0:
            for model in DEFAULT_MODELS:
                repo.create(
                    provider=model.provider,
                    name=model.name,
                    model_type=model.model_type,
                    full_name=model.full_name,
                    bedrock_id=model.bedrock_id,
                    context_window=model.context_window,
                )
            db.commit()
            logfire.info(f"Startup: Seeded {len(DEFAULT_MODELS)} default language model(s)")
        else:
            logfire.info("Startup: Language models table already populated, skipping seed")
    except Exception as e:
        # Fail-soft: log and continue startup rather than blocking the application.
        # Models can be added manually via the API if seeding fails.
        logfire.error(f"Error seeding language models: {e}")
        db.rollback()
    finally:
        db.close()


async def cleanup_stale_locks_on_startup():
    """Cleanup stale worktree locks from crashed/stopped agents on startup.

    Releases locks for tasks with no active conversations and locks older than 24 hours.
    Does NOT perform worktree reconciliation - assumes worktrees are application-managed only.
    """
    db = SessionLocal()
    try:
        codebase_repo = CodebaseRepository(db)
        worktree_slot_repo = WorktreeSlotRepository(db)
        worktree_pool_manager = WorktreePoolManager(worktree_slot_repo=worktree_slot_repo)

        # Get all codebases
        codebases = codebase_repo.get_all()

        total_released = 0
        for codebase in codebases:
            try:
                released = await worktree_pool_manager.cleanup_stale_locks(codebase.id)
                if released > 0:
                    logfire.info(f"Released {released} stale lock(s) for codebase {codebase.name}")
                total_released += released
            except Exception as e:
                # Log error but continue with other codebases
                logfire.error(f"Error cleaning up locks for codebase {codebase.name}: {e}")

        if total_released > 0:
            logfire.info(f"Startup: Released {total_released} stale lock(s) total")
        else:
            logfire.info("Startup: No stale locks found")

        # Commit all changes
        db.commit()
    except Exception as e:
        logfire.error(f"Error during startup lock cleanup: {e}")
        db.rollback()
    finally:
        db.close()


class RequestLifecycleMiddleware:
    """Log when requests arrive and complete with elapsed time."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]
        pool = engine.pool.status()
        logfire.info(f"Request started: {method} {path} [db_pool: {pool}]")
        start = time.monotonic()
        status_code: int | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)
        elapsed_ms = (time.monotonic() - start) * 1000
        logfire.info(f"Request finished: {method} {path} status={status_code} elapsed={elapsed_ms:.0f}ms")


app = FastAPI(
    title="DevBoard API",
    description="AI-powered developer command centre",
    version="0.1.0",
    lifespan=combined_lifespan,
)

setup_logfire(app)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    logfire.warning(f"ValueError in request {request.method} {request.url.path}: {exc}")
    return JSONResponse({"detail": str(exc)}, status_code=400)


# Configure CORS - allow all localhost ports in development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://localhost:\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLifecycleMiddleware)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(codebases.router, prefix="/api/codebases", tags=["codebases"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(configurations.router, prefix="/api/configurations", tags=["configurations"])
app.include_router(custom_fields.router, prefix="/api/custom-fields", tags=["custom-fields"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(background_agents.router, prefix="/api/background-agents", tags=["background-agents"])
app.include_router(background_agent_runs.router, prefix="/api/background-agent-runs", tags=["background-agent-runs"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(websocket.router, prefix="/api", tags=["websocket"])
app.include_router(worktrees.router, prefix="/api", tags=["worktrees"])
app.include_router(tool_approvals.router, prefix="/api")
app.include_router(oauth.router, prefix="/api/oauth", tags=["oauth"])
app.include_router(mcp_servers.router, prefix="/api/mcp-servers", tags=["mcp-servers"])
app.include_router(claude_code.router, prefix="/api/claude-code", tags=["claude-code"])
app.include_router(github.router, prefix="/api/github", tags=["github"])
app.include_router(log_entries.router, prefix="/api/log-entries", tags=["log-entries"])
app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
app.include_router(language_models.router, prefix="/api/language-models", tags=["language-models"])
app.include_router(global_context.router, prefix="/api/global-context", tags=["global-context"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "DevBoard API is running"}
