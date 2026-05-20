"""Tests for agent engine configurations."""

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from devboard.config.agent_engine_configs import ClaudeCodeEngineConfig, ClientMode


class TestClaudeCodeEngineConfig:
    """Tests for ClaudeCodeEngineConfig."""

    def test_default_instantiation(self):
        """Test default instantiation gives sdk mode."""
        config = ClaudeCodeEngineConfig()
        assert config.client_mode == ClientMode.SDK

    def test_explicit_sdk_mode(self):
        """Test explicit SDK mode."""
        config = ClaudeCodeEngineConfig(client_mode=ClientMode.SDK)
        assert config.client_mode == ClientMode.SDK

    def test_interactive_mode_with_tmux_available(self):
        """Test interactive mode when tmux is available."""
        with patch("shutil.which", return_value="/usr/bin/tmux"):
            config = ClaudeCodeEngineConfig(client_mode=ClientMode.INTERACTIVE)
            assert config.client_mode == ClientMode.INTERACTIVE

    def test_interactive_mode_without_tmux(self):
        """Test interactive mode without tmux raises ValidationError."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(ValidationError) as exc_info:
                ClaudeCodeEngineConfig(client_mode=ClientMode.INTERACTIVE)

            errors = exc_info.value.errors()
            assert len(errors) > 0
            assert "client_mode" in str(errors[0]["loc"])
            # Check that the error message mentions tmux
            error_msg = str(errors[0])
            assert "tmux" in error_msg

    def test_invalid_client_mode_value(self):
        """Test invalid client_mode value raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ClaudeCodeEngineConfig(client_mode="invalid")  # type: ignore

        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_config_key(self):
        """Test that config_key is correctly set."""
        assert ClaudeCodeEngineConfig.config_key == "agents.claude_code"

    def test_env_prefix(self):
        """Test that env_prefix is correctly set."""
        assert ClaudeCodeEngineConfig.env_prefix == "CLAUDE_CODE_ENGINE_"

    def test_client_mode_enum_values(self):
        """Test ClientMode enum has correct values."""
        assert ClientMode.SDK.value == "sdk"
        assert ClientMode.INTERACTIVE.value == "interactive"
