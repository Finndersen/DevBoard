"""Tests for CodebaseIntegration write and edit methods."""

from pathlib import Path

import pytest

from devboard.integrations.codebase import CodebaseIntegration


@pytest.fixture
def temp_codebase(tmp_path):
    """Create a temporary codebase directory."""
    codebase_path = tmp_path / "test_codebase"
    codebase_path.mkdir()

    # Create .git directory
    (codebase_path / ".git").mkdir()

    return codebase_path


@pytest.fixture
def codebase_integration(temp_codebase):
    """Create CodebaseIntegration instance."""
    return CodebaseIntegration(temp_codebase)


class TestWriteFile:
    """Tests for write_file method."""

    @pytest.mark.asyncio
    async def test_write_new_file(self, codebase_integration, temp_codebase):
        """Test writing a new file."""
        file_path = "test.txt"
        content = "Hello, World!"

        await codebase_integration.write_file(file_path, content)

        # Verify file was created with correct content
        created_file = temp_codebase / file_path
        assert created_file.exists()
        assert created_file.read_text() == content

    @pytest.mark.asyncio
    async def test_write_file_with_subdirectory(self, codebase_integration, temp_codebase):
        """Test writing a file in a subdirectory that doesn't exist."""
        file_path = "docs/api/endpoints.md"
        content = "# API Endpoints"

        await codebase_integration.write_file(file_path, content)

        # Verify file and directories were created
        created_file = temp_codebase / file_path
        assert created_file.exists()
        assert created_file.read_text() == content

    @pytest.mark.asyncio
    async def test_write_file_overwrites_existing(self, codebase_integration, temp_codebase):
        """Test writing to an existing file overwrites it."""
        file_path = "existing.txt"
        initial_content = "Initial content"
        new_content = "New content"

        # Create initial file
        (temp_codebase / file_path).write_text(initial_content)

        # Overwrite with new content
        await codebase_integration.write_file(file_path, new_content)

        # Verify content was overwritten
        assert (temp_codebase / file_path).read_text() == new_content

    @pytest.mark.asyncio
    async def test_write_file_outside_codebase_fails(self, codebase_integration):
        """Test writing a file outside codebase directory fails."""
        file_path = "../outside.txt"
        content = "This should fail"

        with pytest.raises(ValueError, match="outside codebase directory"):
            await codebase_integration.write_file(file_path, content)


class TestEditFile:
    """Tests for edit_file method."""

    @pytest.mark.asyncio
    async def test_edit_file_single_occurrence(self, codebase_integration, temp_codebase):
        """Test editing a file with single occurrence replacement."""
        file_path = "test.txt"
        original_content = "Hello, World!\nHello, Python!"
        (temp_codebase / file_path).write_text(original_content)

        await codebase_integration.edit_file(
            file_path=file_path, find="Hello, World!", replace="Goodbye, World!", replace_all=False
        )

        # Only first occurrence should be replaced
        expected = "Goodbye, World!\nHello, Python!"
        assert (temp_codebase / file_path).read_text() == expected

    @pytest.mark.asyncio
    async def test_edit_file_all_occurrences(self, codebase_integration, temp_codebase):
        """Test editing a file with all occurrences replacement."""
        file_path = "test.txt"
        original_content = "Hello, World!\nHello, Python!"
        (temp_codebase / file_path).write_text(original_content)

        await codebase_integration.edit_file(
            file_path=file_path, find="Hello", replace="Goodbye", replace_all=True
        )

        # All occurrences should be replaced
        expected = "Goodbye, World!\nGoodbye, Python!"
        assert (temp_codebase / file_path).read_text() == expected

    @pytest.mark.asyncio
    async def test_edit_file_multiline_pattern(self, codebase_integration, temp_codebase):
        """Test editing a file with multiline pattern."""
        file_path = "test.md"
        original_content = "# Title\n\nOld section\n\n## Next"
        (temp_codebase / file_path).write_text(original_content)

        await codebase_integration.edit_file(
            file_path=file_path, find="# Title\n\nOld section", replace="# Title\n\nNew section", replace_all=False
        )

        expected = "# Title\n\nNew section\n\n## Next"
        assert (temp_codebase / file_path).read_text() == expected

    @pytest.mark.asyncio
    async def test_edit_file_not_found_fails(self, codebase_integration):
        """Test editing a non-existent file fails."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            await codebase_integration.edit_file(file_path="missing.txt", find="old", replace="new")

    @pytest.mark.asyncio
    async def test_edit_file_pattern_not_found_fails(self, codebase_integration, temp_codebase):
        """Test editing with pattern that doesn't exist fails."""
        file_path = "test.txt"
        (temp_codebase / file_path).write_text("Hello, World!")

        with pytest.raises(ValueError, match="Find text not found"):
            await codebase_integration.edit_file(file_path=file_path, find="Missing text", replace="new")

    @pytest.mark.asyncio
    async def test_edit_file_outside_codebase_fails(self, codebase_integration):
        """Test editing a file outside codebase directory fails."""
        with pytest.raises(ValueError, match="outside codebase directory"):
            await codebase_integration.edit_file(file_path="../outside.txt", find="old", replace="new")

    @pytest.mark.asyncio
    async def test_edit_file_directory_fails(self, codebase_integration, temp_codebase):
        """Test editing a directory path fails."""
        dir_path = "subdir"
        (temp_codebase / dir_path).mkdir()

        with pytest.raises(ValueError, match="not a file"):
            await codebase_integration.edit_file(file_path=dir_path, find="old", replace="new")
