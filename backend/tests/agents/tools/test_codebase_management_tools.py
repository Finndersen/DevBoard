"""Tests for codebase management tool factories."""

import json
from unittest.mock import Mock

import pytest
from pydantic_ai import ModelRetry

from devboard.agents.tools.codebase_management_tools import (
    create_update_codebase_tool,
    create_view_codebase_details_tool,
)
from devboard.db.models import Codebase
from devboard.db.repositories.codebase import CodebaseRepository


@pytest.fixture
def mock_codebase_alpha():
    cb = Mock(spec=Codebase)
    cb.id = 1
    cb.name = "alpha"
    cb.description = "Alpha service"
    cb.repository_url = "https://github.com/org/alpha"
    cb.local_path = "/repos/alpha"
    cb.default_branch = "main"
    cb.merge_method = "squash"
    cb.branch_handling = "github_pr"
    cb.max_worktrees = 3
    cb.setup_command = "make install"
    cb.developer_context = "Alpha developer notes"
    return cb


@pytest.fixture
def mock_codebase_beta():
    cb = Mock(spec=Codebase)
    cb.id = 2
    cb.name = "beta"
    cb.description = "Beta service"
    cb.repository_url = None
    cb.local_path = "/repos/beta"
    cb.default_branch = "develop"
    cb.merge_method = "merge_commit"
    cb.branch_handling = "direct_merge"
    cb.max_worktrees = None
    cb.setup_command = None
    cb.developer_context = None
    return cb


@pytest.fixture
def mock_codebase_repo():
    repo = Mock(spec=CodebaseRepository)
    repo.db = Mock()
    return repo


class TestViewCodebaseDetails:
    @pytest.mark.asyncio
    async def test_returns_all_fields(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_view_codebase_details_tool([mock_codebase_alpha], mock_codebase_repo)
        result = await tool.function(codebase_name="alpha")
        data = json.loads(result)
        assert data == {
            "id": 1,
            "name": "alpha",
            "description": "Alpha service",
            "repository_url": "https://github.com/org/alpha",
            "local_path": "/repos/alpha",
            "default_branch": "main",
            "merge_method": "squash",
            "branch_handling": "github_pr",
            "max_worktrees": 3,
            "setup_command": "make install",
            "developer_context": "Alpha developer notes",
        }

    @pytest.mark.asyncio
    async def test_nullable_fields_returned_as_none(self, mock_codebase_beta, mock_codebase_repo):
        tool = create_view_codebase_details_tool([mock_codebase_beta], mock_codebase_repo)
        result = await tool.function(codebase_name="beta")
        data = json.loads(result)
        assert data == {
            "id": 2,
            "name": "beta",
            "description": "Beta service",
            "repository_url": None,
            "local_path": "/repos/beta",
            "default_branch": "develop",
            "merge_method": "merge_commit",
            "branch_handling": "direct_merge",
            "max_worktrees": None,
            "setup_command": None,
            "developer_context": None,
        }

    @pytest.mark.asyncio
    async def test_selects_correct_codebase_from_multiple(
        self, mock_codebase_alpha, mock_codebase_beta, mock_codebase_repo
    ):
        tool = create_view_codebase_details_tool([mock_codebase_alpha, mock_codebase_beta], mock_codebase_repo)
        result = await tool.function(codebase_name="beta")
        data = json.loads(result)
        assert data["name"] == "beta"

    @pytest.mark.asyncio
    async def test_codebase_not_found_raises_model_retry(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_view_codebase_details_tool([mock_codebase_alpha], mock_codebase_repo)
        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(codebase_name="nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "alpha" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_codebases_raises_model_retry(self, mock_codebase_repo):
        tool = create_view_codebase_details_tool([], mock_codebase_repo)
        with pytest.raises(ModelRetry):
            await tool.function(codebase_name="anything")


class TestUpdateCodebase:
    @pytest.mark.asyncio
    async def test_update_description(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_update_codebase_tool([mock_codebase_alpha], mock_codebase_repo)
        result = await tool.function(codebase_name="alpha", description="Updated description")
        data = json.loads(result)
        assert data == {"id": 1, "name": "alpha", "description": "Updated description"}
        assert mock_codebase_alpha.description == "Updated description"
        mock_codebase_repo.update.assert_called_once_with(mock_codebase_alpha)
        mock_codebase_repo.db.commit.assert_called_once()
        mock_codebase_repo.db.refresh.assert_called_once_with(mock_codebase_alpha)

    @pytest.mark.asyncio
    async def test_update_setup_command(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_update_codebase_tool([mock_codebase_alpha], mock_codebase_repo)
        result = await tool.function(codebase_name="alpha", setup_command="npm install")
        data = json.loads(result)
        assert data == {"id": 1, "name": "alpha", "setup_command": "npm install"}
        assert mock_codebase_alpha.setup_command == "npm install"

    @pytest.mark.asyncio
    async def test_update_developer_context(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_update_codebase_tool([mock_codebase_alpha], mock_codebase_repo)
        result = await tool.function(codebase_name="alpha", developer_context="New developer notes")
        data = json.loads(result)
        assert data == {"id": 1, "name": "alpha", "developer_context": "New developer notes"}
        assert mock_codebase_alpha.developer_context == "New developer notes"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_update_codebase_tool([mock_codebase_alpha], mock_codebase_repo)
        result = await tool.function(codebase_name="alpha", description="New desc", setup_command="yarn install")
        data = json.loads(result)
        assert data == {"id": 1, "name": "alpha", "description": "New desc", "setup_command": "yarn install"}

    @pytest.mark.asyncio
    async def test_no_fields_raises_model_retry(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_update_codebase_tool([mock_codebase_alpha], mock_codebase_repo)
        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(codebase_name="alpha")
        assert "No fields to update" in str(exc_info.value)
        mock_codebase_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_selects_correct_codebase_from_multiple(
        self, mock_codebase_alpha, mock_codebase_beta, mock_codebase_repo
    ):
        tool = create_update_codebase_tool([mock_codebase_alpha, mock_codebase_beta], mock_codebase_repo)
        result = await tool.function(codebase_name="beta", description="Beta updated")
        data = json.loads(result)
        assert data == {"id": 2, "name": "beta", "description": "Beta updated"}
        assert mock_codebase_beta.description == "Beta updated"
        mock_codebase_repo.update.assert_called_once_with(mock_codebase_beta)

    @pytest.mark.asyncio
    async def test_codebase_not_found_raises_model_retry(self, mock_codebase_alpha, mock_codebase_repo):
        tool = create_update_codebase_tool([mock_codebase_alpha], mock_codebase_repo)
        with pytest.raises(ModelRetry) as exc_info:
            await tool.function(codebase_name="ghost", description="update")
        assert "ghost" in str(exc_info.value)
        mock_codebase_repo.update.assert_not_called()
