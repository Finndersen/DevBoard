"""Main FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from devboard.api.routers import (
    agents,
    codebases,
    configurations,
    conversations,
    custom_fields,
    documents,
    filesystem,
    oauth,
    projects,
    settings,
    tasks,
    tool_approvals,
    worktrees,
)
from devboard.config.logfire_config import setup_logfire
from devboard.db.database import SessionLocal
from devboard.db.repositories.codebase import CodebaseRepository
from devboard.db.repositories.conversation import ConversationRepository
from devboard.db.repositories.task import TaskRepository
from devboard.db.repositories.worktree_slot import WorktreeSlotRepository
from devboard.mcp import mcp
from devboard.services.workspace_allocation_service import WorkspaceAllocationService

"""Load environment variables from .env files in current directory or home directory."""
load_dotenv(Path.cwd() / ".env", override=False)
load_dotenv(Path.home() / ".env", override=False)


class SingleSessionMCP:
    """Wrapper which prevents error of initialising FastMCP's StreamableHTTPSessionManager multiple times during tests."""

    def __init__(self, mcp: FastMCP):
        self.app = mcp.http_app(path="/mcp", transport="http")
        self.lifespan_generator = self.app.lifespan(self.app)
        self.generator_started = False

    async def start_session(self):
        if self.generator_started:
            return
        await self.lifespan_generator.__aenter__()
        self.generator_started = True

    async def stop_session(self):
        if not self.generator_started:
            return
        await self.lifespan_generator.__aexit__(None, None, None)
        self.generator_started = False


ss_mcp = SingleSessionMCP(mcp)


@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    """Run both lifespans."""
    await ss_mcp.start_session()
    await cleanup_stale_locks_on_startup()
    try:
        yield
    finally:
        await ss_mcp.stop_session()


async def cleanup_stale_locks_on_startup():
    """Cleanup stale worktree locks from crashed/stopped agents on startup.

    Releases locks for tasks with no active conversations and locks older than 24 hours.
    Does NOT perform worktree reconciliation - assumes worktrees are application-managed only.
    """
    db = SessionLocal()
    try:
        codebase_repo = CodebaseRepository(db)
        task_repo = TaskRepository(db)
        worktree_slot_repo = WorktreeSlotRepository(db)
        conversation_repo = ConversationRepository(db)

        workspace_service = WorkspaceAllocationService(
            worktree_slot_repo=worktree_slot_repo,
            task_repo=task_repo,
            conversation_repo=conversation_repo,
        )

        # Get all codebases
        codebases = codebase_repo.get_all()

        total_released = 0
        for codebase in codebases:
            try:
                released = await workspace_service.cleanup_stale_locks(codebase.id)
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


app = FastAPI(
    title="DevBoard API",
    description="AI-powered developer command centre",
    version="0.1.0",
    lifespan=combined_lifespan,
)

setup_logfire(app)

# Configure CORS - allow all localhost ports in development
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://localhost:\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(codebases.router, prefix="/api/codebases", tags=["codebases"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(configurations.router, prefix="/api/configurations", tags=["configurations"])
app.include_router(custom_fields.router, prefix="/api/custom-fields", tags=["custom-fields"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(worktrees.router, prefix="/api", tags=["worktrees"])
app.include_router(tool_approvals.router, prefix="/api")
app.include_router(oauth.router, prefix="/api/oauth", tags=["oauth"])
app.include_router(filesystem.router, prefix="/api/filesystem", tags=["filesystem"])

# Mount MCP server as ASGI application
# The MCP server handles requests to /mcp/sse (SSE transport) and /mcp/messages (Streamable HTTP)
app.mount("/mcp", ss_mcp.app)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "DevBoard API is running"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "database": "connected",  # TODO: Add actual database health check
    }
