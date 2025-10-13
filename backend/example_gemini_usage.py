"""Example usage of the enhanced Gemini CLI executor."""

import asyncio
from pathlib import Path

from devboard.agents.engines.gemini_cli import execute_gemini_prompt


async def example_usage():
    """Demonstrate different ways to use the enhanced Gemini CLI executor."""

    # Example 1: Basic usage with required model parameter
    print("=== Example 1: Basic usage ===")
    try:
        response = await execute_gemini_prompt(prompt="What is the capital of France?", model="gemini-2.5-flash")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Read-only mode with custom working directory
    print("\n=== Example 2: Read-only mode ===")
    try:
        response = await execute_gemini_prompt(
            prompt="Explain what Python is in one sentence.",
            model="gemini-1.5-pro",
            working_dir="/tmp",
            timeout=30.0,
            operation_mode="read_only",
        )
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 3: Codebase analysis with read-only mode
    print("\n=== Example 3: Codebase analysis (read-only) ===")
    try:
        analysis_prompt = """
Analyze this Python project structure and tell me what type of application it is.
Look at the directory structure, key files, and imports to determine the purpose.
Only read and analyze files - do not make any modifications.
"""

        response = await execute_gemini_prompt(
            prompt=analysis_prompt,
            model="gemini-2.5-flash",  # Fast model for code analysis
            working_dir=Path.cwd(),
            timeout=60.0,
            operation_mode="read_only",  # Restrict to read-only tools
        )
        print(f"Analysis: {response}")

    except Exception as e:
        print(f"Error: {e}")

    # Example 4: Read & write mode for code generation/modification
    print("\n=== Example 4: Code generation (read-write) ===")
    try:
        generation_prompt = """
Create a simple Python utility function that calculates the factorial of a number.
Save it to a file called 'factorial_util.py' in the current directory.
"""

        response = await execute_gemini_prompt(
            prompt=generation_prompt,
            model="gemini-2.5-flash",
            working_dir=Path.cwd(),
            timeout=30.0,
            operation_mode="read_write",  # Allow file creation and modification
        )
        print(f"Generation result: {response}")

    except Exception as e:
        print(f"Error: {e}")

    # Example 5: Different models for different tasks
    print("\n=== Example 5: Using different models ===")

    models_and_prompts = [
        ("gemini-2.5-flash", "Quick question: What's 2+2?"),  # Fast model for simple tasks
        (
            "gemini-1.5-pro",
            "Explain the concept of async programming in detail.",
        ),  # More capable model
        (
            "gemini-2.5-flash",
            "List the files in the current directory",
        ),  # Fast model for tool usage
    ]

    for model, prompt in models_and_prompts:
        try:
            response = await execute_gemini_prompt(prompt=prompt, model=model, timeout=20.0, operation_mode="read_only")
            print(f"Model {model}: {response[:100]}...")  # Truncate for readability
        except Exception as e:
            print(f"Error with {model}: {e}")

    # Example 6: Error handling for invalid parameters
    print("\n=== Example 6: Error handling ===")
    try:
        response = await execute_gemini_prompt(
            prompt="Test prompt",
            model="gemini-2.5-flash",
            operation_mode="invalid_mode",  # This should raise ValueError
        )
    except ValueError as e:
        print(f"Expected ValueError: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    # Note: This example requires gemini-cli to be installed
    # Install with: npm install -g @google/generative-ai-cli
    # Or follow instructions at: https://github.com/google-gemini/gemini-cli
    asyncio.run(example_usage())
