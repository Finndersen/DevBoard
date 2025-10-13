"""Async wrapper for gemini-cli single-prompt execution."""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Define read-only tools
READ_ONLY_TOOLS = [
    "LSTool",
    "ReadFileTool",
    "GrepTool",
    "GlobTool",
    "ReadManyFilesTool",
    "WebFetchTool",
    "WebSearchTool",
    "MemoryTool",
    # Read-only shell commands
    "ShellTool(ls)",
    "ShellTool(find)",
    "ShellTool(cat)",
    "ShellTool(head)",
    "ShellTool(tail)",
    "ShellTool(grep)",
    "ShellTool(rg)",  # ripgrep
    "ShellTool(fd)",  # fd-find
    "ShellTool(ast-grep)",
    "ShellTool(readlink)",
    "ShellTool(pwd)",
    "ShellTool(which)",
    "ShellTool(file)",
    "ShellTool(wc)",
    "ShellTool(du)",
    "ShellTool(tree)",
    "ShellTool(git status)",
    "ShellTool(git log)",
    "ShellTool(git diff)",
    "ShellTool(git branch)",
    "ShellTool(git remote)",
    "ShellTool(git show)",
    "ShellTool(git rev-list)",
    "ShellTool(git merge-base)",
    "ShellTool(curl)",
    "ShellTool(wget)",
]

# Define read-write tools (includes all read-only tools plus write operations)
READ_WRITE_TOOLS = READ_ONLY_TOOLS + [
    "WriteFileTool",
    "EditTool",
    # Write-capable shell commands
    "ShellTool(mkdir)",
    "ShellTool(mv)",
    "ShellTool(cp)",
    "ShellTool(rm)",
    "ShellTool(sed)",
    "ShellTool(awk)",
    "ShellTool(git add)",
    "ShellTool(git commit)",
    "ShellTool(git push)",
    "ShellTool(git pull)",
    "ShellTool(git checkout)",
    "ShellTool(git merge)",
    "ShellTool(git rebase)",
]


class GeminiCliError(Exception):
    """Base exception for Gemini CLI errors."""

    pass


class GeminiCliTimeoutError(GeminiCliError):
    """Gemini CLI timeout error."""

    pass


class GeminiCliNotFoundError(GeminiCliError):
    """Gemini CLI not found error."""

    pass


class GeminiCliExecutionError(GeminiCliError):
    """Gemini CLI execution error."""

    pass


async def execute_gemini_prompt(
    prompt: str,
    model: str,
    working_dir: str | Path | None = None,
    timeout: float = 60.0,
    operation_mode: str = "read_write",
) -> str:
    """Execute a single prompt using gemini-cli asynchronously.

    Args:
        prompt: The prompt to send to Gemini
        model: The Gemini model to use (e.g., 'gemini-2.5-flash', 'gemini-1.5-pro')
        working_dir: Working directory for the command (default: current directory)
        timeout: Command timeout in seconds (default: 60)
        operation_mode: Tool access mode - 'read_only' or 'read_write' (default: 'read_write')

    Returns:
        The response from Gemini as a string

    Raises:
        GeminiCliNotFoundError: If gemini-cli is not found
        GeminiCliTimeoutError: If the command times out
        GeminiCliExecutionError: If the command fails with an error
        ValueError: If invalid operation_mode is provided
    """
    # Validate operation mode
    if operation_mode not in ["read_only", "read_write"]:
        raise ValueError(f"Invalid operation_mode: {operation_mode}. Must be 'read_only' or 'read_write'")

    # Resolve working directory
    if working_dir:
        cwd = str(Path(working_dir).resolve())
    else:
        cwd = str(Path.cwd())

    logger.debug(f"Executing gemini prompt in {cwd} with model {model}, mode {operation_mode}, timeout {timeout}s")

    try:
        # Build command arguments
        args = ["gemini", "-p", prompt.strip(), "-m", model]

        # Add tool restrictions based on operation mode
        if operation_mode == "read_only":
            allowed_tools = ",".join(READ_ONLY_TOOLS)
            args.extend(["--allowed-tools", allowed_tools])
        elif operation_mode == "read_write":
            allowed_tools = ",".join(READ_WRITE_TOOLS)
            args.extend(["--allowed-tools", allowed_tools])

        # Create the subprocess asynchronously
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError as e:
            # Kill the process if it's still running
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass  # Process already terminated

            logger.error(f"Gemini CLI timed out after {timeout}s")
            raise GeminiCliTimeoutError(f"Gemini CLI timed out after {timeout} seconds") from e

        # Decode output
        stdout_text = stdout.decode("utf-8").strip()
        stderr_text = stderr.decode("utf-8").strip()

        # Check return code
        if process.returncode == 0:
            logger.info(f"Gemini CLI prompt executed successfully (model: {model}, mode: {operation_mode})")
            return stdout_text
        else:
            error_msg = stderr_text or "Unknown error"
            logger.error(f"Gemini CLI failed with return code {process.returncode}: {error_msg}")
            raise GeminiCliExecutionError(f"Gemini CLI error: {error_msg}")

    except FileNotFoundError as e:
        logger.error("Gemini CLI not found - ensure gemini is installed and in PATH")
        raise GeminiCliNotFoundError(
            "Gemini CLI not installed - install from https://github.com/google-gemini/gemini-cli"
        ) from e
    except Exception as e:
        if isinstance(e, GeminiCliError):
            raise
        logger.error(f"Unexpected error executing gemini-cli: {e}")
        raise GeminiCliExecutionError(f"Unexpected error: {e}") from e
