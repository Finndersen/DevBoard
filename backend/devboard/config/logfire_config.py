"""Logfire configuration for DevBoard application."""

import os

import logfire
from fastapi import FastAPI


def setup_logfire(app: FastAPI) -> None:
    """Setup Logfire configuration. Call this once at application startup."""

    # Check if Logfire token is available in environment
    token = os.getenv("LOGFIRE_TOKEN")
    environment = os.getenv("ENVIRONMENT", "development")

    # Configure Logfire with hardcoded sensible defaults
    logfire.configure(
        service_name="devboard",
        service_version="0.1.0",
        environment=environment,
        console={"verbose": environment == "development"},
        # Only send to Logfire if we have a token (production/staging) or in development with explicit token
        send_to_logfire=bool(token)
    )

    # Enable instrumentation that doesn't require parameters
    logfire.instrument_sqlalchemy()
    logfire.instrument_httpx()
    logfire.instrument_fastapi(app)

