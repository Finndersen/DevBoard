"""Configuration classes for AI agent engines."""

import shutil
from enum import StrEnum

from pydantic import field_validator

from devboard.config.base import BaseConfig


class ClientMode(StrEnum):
    """Client mode for Claude Code engine."""

    SDK = "sdk"
    INTERACTIVE = "interactive"


class ClaudeCodeEngineConfig(BaseConfig):
    """Configuration for Claude Code agent engine.

    Controls whether to use headless SDK mode (API key billing) or
    interactive terminal mode (subscription billing via tmux).
    """

    config_key = "agents.claude_code"
    env_prefix = "CLAUDE_CODE_ENGINE_"

    client_mode: ClientMode = ClientMode.SDK
    """Whether to use SDK mode (api key, 'sdk') or interactive mode (subscription, 'interactive')."""

    @field_validator("client_mode")
    @classmethod
    def validate_interactive_mode(cls, v: ClientMode) -> ClientMode:
        """Validate that tmux is available when using interactive mode."""
        if v == ClientMode.INTERACTIVE and not shutil.which("tmux"):
            raise ValueError("tmux is required for interactive mode but was not found on PATH")
        return v
