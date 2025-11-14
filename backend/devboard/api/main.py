"""Main FastAPI application."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devboard.api.routers import (
    agents,
    codebases,
    configurations,
    conversations,
    projects,
    settings,
    tasks,
    tool_approvals,
)
from devboard.api.routers.mcp import mcp_app
from devboard.config.logfire_config import setup_logfire

"""Load environment variables from .env files in current directory or home directory."""
load_dotenv(Path.cwd() / ".env", override=False)
load_dotenv(Path.home() / ".env", override=False)

# logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="DevBoard API",
    description="AI-powered developer command centre",
    version="0.1.0",
    lifespan=mcp_app.lifespan,  # Pass MCP lifespan for proper initialization
)

setup_logfire(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(codebases.router, prefix="/api/codebases", tags=["codebases"])
app.include_router(configurations.router, prefix="/api/configurations", tags=["configurations"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(tool_approvals.router, prefix="/api")

# Mount MCP server as ASGI application
# The MCP server handles requests to /mcp/sse (SSE transport) and /mcp/messages (Streamable HTTP)
app.mount("/mcp", mcp_app)


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
