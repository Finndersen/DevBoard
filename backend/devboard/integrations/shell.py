"""Async shell command execution utility."""

import asyncio
from pathlib import Path

import logfire


class ShellCommandError(Exception):
    """Base exception for shell command errors."""

    pass


class ShellCommandTimeoutError(ShellCommandError):
    """Shell command timeout error."""

    pass


class ShellCommandNotFoundError(ShellCommandError):
    """Shell command not found error."""

    pass


class ShellCommandExecutionError(ShellCommandError):
    """Shell command execution error."""

    pass


class ShellCommandResult:
    """Result of shell command execution."""

    def __init__(self, stdout: str, stderr: str, returncode: int):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    @property
    def success(self) -> bool:
        """Check if command executed successfully."""
        return self.returncode == 0


async def execute_shell_command(
    command: list[str],
    working_dir: str | Path | None = None,
    timeout: float = 30.0,
    raise_on_error: bool = True,
) -> ShellCommandResult:
    """Execute a shell command asynchronously.

    Args:
        command: Command and arguments as a list (e.g., ['ls', '-la']).
                If the list contains a single string with shell syntax (pipes, redirects),
                it will be executed through a shell.
        working_dir: Working directory for the command (default: current directory)
        timeout: Command timeout in seconds (default: 30)
        raise_on_error: Whether to raise exception on non-zero return code (default: True)

    Returns:
        ShellCommandResult with stdout, stderr, and return code

    Raises:
        ShellCommandNotFoundError: If command is not found
        ShellCommandTimeoutError: If the command times out
        ShellCommandExecutionError: If the command fails and raise_on_error is True
    """
    if not command:
        raise ValueError("Command cannot be empty")

    if working_dir:
        cwd = str(Path(working_dir).resolve())
        if not Path(cwd).is_dir():
            raise ValueError(f"Working directory does not exist: {cwd}")
    else:
        cwd = str(Path.cwd())

    # Determine if we need shell execution (single string with shell syntax)
    use_shell = len(command) == 1 and ("|" in command[0] or ">" in command[0] or "<" in command[0])
    try:
        if use_shell:
            logfire.debug(f"Executing shell command in {cwd}: {command[0]}, timeout {timeout}s")
            process = await asyncio.create_subprocess_shell(
                command[0],
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
        else:
            logfire.debug(f"Executing shell command in {cwd}: {' '.join(command)}, timeout {timeout}s")
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError as e:
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass

            raise ShellCommandTimeoutError(f"Command timed out after {timeout} seconds: {command[0]}") from e

        stdout_text = stdout.decode("utf-8")
        stderr_text = stderr.decode("utf-8")

        result = ShellCommandResult(stdout_text, stderr_text, process.returncode)

        if not result.success and raise_on_error:
            error_msg = stderr_text.strip() or f"Command failed with return code {process.returncode}"
            logfire.error(f"Shell command failed: {' '.join(command)} - {error_msg}")
            raise ShellCommandExecutionError(f"Command '{command[0]}' failed: {error_msg}")

        logfire.debug(f"Shell command completed successfully: {command[0]}")
        return result
    except FileNotFoundError as e:
        logfire.error(f"Shell command not found: {command[0]}")
        raise ShellCommandNotFoundError(f"Command not found: {command[0]}") from e
