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

    if os.getenv("DISABLE_LOGFIRE", "").lower() in ("1", "true", "yes"):
        # Keep console output for local visibility, but skip cloud export and all
        # instrumentation hooks — used to isolate whether logfire's background
        # exporter or instrumentation callbacks are causing event loop blocking.
        environment = os.getenv("ENVIRONMENT", "development")
        log_level: LevelName = cast(
            LevelName, os.getenv("LOG_LEVEL", "info" if environment == "production" else "debug")
        )
        console_options: ConsoleOptions | bool = (
            ConsoleOptions(verbose=True, min_log_level=log_level) if environment == "development" else False
        )
        logfire.configure(send_to_logfire=False, console=console_options)
        return

    environment = os.getenv("ENVIRONMENT", "development")
    log_level: LevelName = cast(LevelName, os.getenv("LOG_LEVEL", "info" if environment == "production" else "debug"))

    # Configure console options for development
    console_options: ConsoleOptions | bool = False
    if environment == "development":
        console_options = ConsoleOptions(verbose=True, min_log_level=log_level)

    # 'if-token-present' enables cloud export only when LOGFIRE_TOKEN env var or
    # ~/.logfire/default.toml credentials exist — silently skips otherwise.
    logfire.configure(
        send_to_logfire="if-token-present",
        service_name="devboard",
        environment=environment,
        console=console_options,
        scrubbing=logfire.ScrubbingOptions(callback=scrubbing_callback),
    )

    # Enable instrumentation that doesn't require parameters
    logfire.instrument_sqlalchemy(engine=engine)
    logfire.instrument_httpx()
    logfire.instrument_fastapi(app)
    logfire.instrument_pydantic_ai()
    logfire.instrument_mcp()
