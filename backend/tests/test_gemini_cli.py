"""Tests for the Gemini CLI utility."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.agents.gemini_cli import (
    GeminiCliExecutionError,
    GeminiCliNotFoundError,
    GeminiCliTimeoutError,
    execute_gemini_prompt,
)


class TestExecuteGeminiPrompt:
    """Test the execute_gemini_prompt function."""

    @pytest.mark.asyncio
    async def test_successful_execution_read_only(self):
        """Test successful execution with read-only mode."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Test response", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_subprocess:
            result = await execute_gemini_prompt(
                prompt="Test prompt", model="gemini-2.5-flash", operation_mode="read_only"
            )

            assert result == "Test response"

            # Verify correct command arguments
            call_args = mock_subprocess.call_args[0]
            assert call_args[0] == "gemini"
            assert call_args[1] == "-p"
            assert call_args[2] == "Test prompt"
            assert call_args[3] == "-m"
            assert call_args[4] == "gemini-2.5-flash"
            assert call_args[5] == "--allowed-tools"
            assert "ReadFileTool" in call_args[6]
            assert "WriteFileTool" not in call_args[6]

    @pytest.mark.asyncio
    async def test_successful_execution_read_write(self):
        """Test successful execution with read-write mode."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Test response", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_subprocess:
            result = await execute_gemini_prompt(
                prompt="Test prompt", model="gemini-1.5-pro", operation_mode="read_write"
            )

            assert result == "Test response"

            # Verify correct command arguments for read-write mode
            call_args = mock_subprocess.call_args[0]
            assert call_args[5] == "--allowed-tools"
            assert "ReadFileTool" in call_args[6]
            assert "WriteFileTool" in call_args[6]
            assert "ShellTool" in call_args[6]

    @pytest.mark.asyncio
    async def test_invalid_operation_mode(self):
        """Test that invalid operation mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid operation_mode"):
            await execute_gemini_prompt(
                prompt="Test prompt", model="gemini-2.5-flash", operation_mode="invalid_mode"
            )

    @pytest.mark.asyncio
    async def test_command_failure(self):
        """Test handling of command failure."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Command failed"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(GeminiCliExecutionError, match="Gemini CLI error: Command failed"):
                await execute_gemini_prompt(prompt="Test prompt", model="gemini-2.5-flash")

    @pytest.mark.asyncio
    async def test_gemini_not_found(self):
        """Test handling when gemini CLI is not found."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            with pytest.raises(GeminiCliNotFoundError, match="Gemini CLI not installed"):
                await execute_gemini_prompt(prompt="Test prompt", model="gemini-2.5-flash")

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling."""
        mock_process = Mock()
        mock_process.kill = Mock()  # kill() is not async
        mock_process.wait = AsyncMock()  # wait() is async

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", side_effect=TimeoutError()):
                with pytest.raises(GeminiCliTimeoutError, match="Gemini CLI timed out"):
                    await execute_gemini_prompt(
                        prompt="Test prompt", model="gemini-2.5-flash", timeout=1.0
                    )

                # Verify process was killed and waited for
                mock_process.kill.assert_called_once()
                mock_process.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_working_directory(self):
        """Test custom working directory parameter."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Test response", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_subprocess:
            await execute_gemini_prompt(
                prompt="Test prompt", model="gemini-2.5-flash", working_dir="/private/tmp"
            )

            # Verify working directory was set
            call_kwargs = mock_subprocess.call_args[1]
            assert call_kwargs["cwd"] == "/private/tmp"
