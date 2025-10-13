"""Logfire configuration for DevBoard application."""

import os

import logfire
from fastapi import FastAPI
from logfire import ConsoleOptions

from devboard.db.database import engine


def scrubbing_callback(m: logfire.ScrubMatch):
    # Dont scrub Claude Code message content
    if m.path == ("attributes", "message", "session_id"):
        return m.value

    if m.path == ("attributes", "message", "result") and m.pattern_match.group(0) == "session":
        return m.value

    if m.path == ("attributes", "message", "content", 0, "text") and m.pattern_match.group(0) == "Session":
        return m.value


def setup_logfire(app: FastAPI) -> None:
    """Setup Logfire configuration. Call this once at application startup."""

    # Check if Logfire token is available in environment
    token = os.getenv("LOGFIRE_TOKEN")
    environment = os.getenv("ENVIRONMENT", "development")

    # Configure Logfire with hardcoded sensible defaults
    logfire.configure(
        service_name="devboard",
        environment=environment,
        console=ConsoleOptions(verbose=True) if environment == "development" else False,
        # Only send to Logfire if we have a token (production/staging) or in development with explicit token
        send_to_logfire=bool(token),
        scrubbing=logfire.ScrubbingOptions(callback=scrubbing_callback),
    )

    # Enable instrumentation that doesn't require parameters
    logfire.instrument_sqlalchemy(engine=engine)
    logfire.instrument_httpx()
    logfire.instrument_fastapi(app)
    logfire.instrument_pydantic_ai()
