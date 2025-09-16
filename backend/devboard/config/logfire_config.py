"""Logfire configuration for DevBoard application."""

import os

import logfire
from fastapi import FastAPI

from devboard.db.database import engine


def setup_logfire(app: FastAPI) -> None:
    """Setup Logfire configuration. Call this once at application startup."""

    # Check if Logfire token is available in environment
    token = os.getenv("LOGFIRE_TOKEN")
    environment = os.getenv("ENVIRONMENT", "development")

    # Configure Logfire with hardcoded sensible defaults
    logfire.configure(
        service_name="devboard",
        environment=environment,
        console={"verbose": True} if environment == "development" else False,
        # Only send to Logfire if we have a token (production/staging) or in development with explicit token
        send_to_logfire=bool(token),
    )

    # Enable instrumentation that doesn't require parameters
    logfire.instrument_sqlalchemy(engine=engine)
    logfire.instrument_httpx()
    logfire.instrument_fastapi(app)
    logfire.instrument_pydantic_ai()
