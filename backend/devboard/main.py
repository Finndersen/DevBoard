"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devboard.routers import projects, tasks, codebases, configurations

app = FastAPI(
    title="DevBoard API",
    description="AI-powered developer command centre",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])  
app.include_router(codebases.router, prefix="/api/codebases", tags=["codebases"])
app.include_router(configurations.router, prefix="/api/configurations", tags=["configurations"])


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
        "database": "connected"  # TODO: Add actual database health check
    }