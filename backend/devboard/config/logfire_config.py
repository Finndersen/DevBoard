"""Logfire configuration for DevBoard application."""

import os
from typing import cast

import logfire
from fastapi import FastAPI
from logfire import ConsoleOptions, LevelName

from devboard.db.database import engine


def scrubbing_callback(m: logfire.ScrubMatch):
    return m.value
    # Dont scrub Claude Code message content
    if m.path == ("attributes", "message", "session_id"):
        return m.value

    if m.path == ("attributes", "system_prompt"):
        return m.value

    if m.path == ("attributes", "message", "result") and m.pattern_match.group(0).lower() == "session":
        return m.value

    if m.path == ("attributes", "message", "content", 0, "text") and m.pattern_match.group(0).lower() in (
        "session",
        "auth",
    ):
        return m.value

    if (
        m.path == ("attributes", "message", "content", 0, "input", "command")
        and m.pattern_match.group(0).lower() == "session"
    ):
        return m.value

    if m.path == ("message", "e") and m.pattern_match.group(0) == "auth":
        return m.value


def setup_logfire(app: FastAPI) -> None:
    """Setup Logfire configuration. Call this once at application startup."""

    # Check if Logfire token is available in environment
    token = os.getenv("LOGFIRE_TOKEN")
    environment = os.getenv("ENVIRONMENT", "development")
    log_level: LevelName = cast(LevelName, os.getenv("LOG_LEVEL", "info" if environment == "production" else "debug"))

    # Configure console options for development
    console_options: ConsoleOptions | bool = False
    if environment == "development":
        console_options = ConsoleOptions(verbose=True, min_log_level=log_level)

    # Configure Logfire with hardcoded sensible defaults
    logfire.configure(
        service_name="devboard",
        environment=environment,
        console=console_options,
        # Only send to Logfire if we have a token (production/staging) or in development with explicit token
        send_to_logfire=bool(token),
        scrubbing=logfire.ScrubbingOptions(callback=scrubbing_callback),
    )

    # Enable instrumentation that doesn't require parameters
    logfire.instrument_sqlalchemy(engine=engine)
    logfire.instrument_httpx()
    logfire.instrument_fastapi(app)
    logfire.instrument_pydantic_ai()
    logfire.instrument_mcp()
