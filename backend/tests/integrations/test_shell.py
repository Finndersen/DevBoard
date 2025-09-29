"""Tests for shell command execution utility."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from devboard.integrations.shell import (
    ShellCommandExecutionError,
    ShellCommandNotFoundError,
    ShellCommandResult,
    ShellCommandTimeoutError,
    execute_shell_command,
)


class TestShellCommandResult:
    """Tests for ShellCommandResult class."""

    def test_success_property_true(self):
        """Test success property returns True when returncode is 0."""
        result = ShellCommandResult("output", "", 0)
        assert result.success is True

    def test_success_property_false(self):
        """Test success property returns False when returncode is non-zero."""
        result = ShellCommandResult("", "error", 1)
        assert result.success is False

    def test_attributes(self):
        """Test result attributes are set correctly."""
        result = ShellCommandResult("stdout text", "stderr text", 42)
        assert result.stdout == "stdout text"
        assert result.stderr == "stderr text"
        assert result.returncode == 42


class TestExecuteShellCommand:
    """Tests for execute_shell_command function."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful command execution."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"test output", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await execute_shell_command(["echo", "test"])

            assert result.success is True
            assert result.stdout == "test output"
            assert result.stderr == ""
            assert result.returncode == 0

            mock_exec.assert_called_once()
            call_args = mock_exec.call_args
            assert call_args[0] == ("echo", "test")

    @pytest.mark.asyncio
    async def test_command_with_working_directory(self):
        """Test command execution with working directory."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"output", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
            result = await execute_shell_command(["ls"], working_dir="/tmp")

            assert result.success is True
            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs["cwd"] == str(Path("/tmp").resolve())

    @pytest.mark.asyncio
    async def test_command_failure_with_raise_on_error(self):
        """Test command failure raises exception when raise_on_error is True."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error message"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(ShellCommandExecutionError) as exc_info:
                await execute_shell_command(["false"], raise_on_error=True)

            assert "error message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_command_failure_without_raise_on_error(self):
        """Test command failure returns result when raise_on_error is False."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error message"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await execute_shell_command(["false"], raise_on_error=False)

            assert result.success is False
            assert result.returncode == 1
            assert result.stderr == "error message"

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        """Test command not found raises ShellCommandNotFoundError."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("Command not found")):
            with pytest.raises(ShellCommandNotFoundError) as exc_info:
                await execute_shell_command(["nonexistent_command"])

            assert "nonexistent_command" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_command_timeout(self):
        """Test command timeout raises ShellCommandTimeoutError."""
        mock_process = Mock()
        mock_process.kill = Mock()  # kill() is synchronous
        mock_process.wait = AsyncMock()  # wait() is async

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", side_effect=TimeoutError()):
                with pytest.raises(ShellCommandTimeoutError):
                    await execute_shell_command(["sleep", "10"], timeout=0.1)

    @pytest.mark.asyncio
    async def test_empty_command_raises_error(self):
        """Test empty command raises ValueError."""
        with pytest.raises(ValueError, match="Command cannot be empty"):
            await execute_shell_command([])

    @pytest.mark.asyncio
    async def test_invalid_working_directory(self):
        """Test invalid working directory raises ValueError."""
        with pytest.raises(ValueError, match="Working directory does not exist"):
            await execute_shell_command(["ls"], working_dir="/nonexistent/path")

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self):
        """Test timeout properly kills the process."""
        mock_process = Mock()
        mock_process.kill = Mock()  # kill() is synchronous
        mock_process.wait = AsyncMock()  # wait() is async

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", side_effect=TimeoutError()):
                with pytest.raises(ShellCommandTimeoutError):
                    await execute_shell_command(["sleep", "10"], timeout=0.1)

                mock_process.kill.assert_called_once()
                mock_process.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_handles_already_terminated_process(self):
        """Test timeout handles ProcessLookupError when process already terminated."""
        mock_process = Mock()
        mock_process.kill = Mock(side_effect=ProcessLookupError())  # kill() is synchronous
        mock_process.wait = AsyncMock()  # wait() is async

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", side_effect=TimeoutError()):
                with pytest.raises(ShellCommandTimeoutError):
                    await execute_shell_command(["sleep", "10"], timeout=0.1)
