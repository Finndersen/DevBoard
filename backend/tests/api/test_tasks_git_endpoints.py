"""Tests for task git endpoint: POST /{task_id}/create-branch."""

from unittest.mock import AsyncMock, patch


class TestCreateTaskBranch:
    """Tests for POST /api/tasks/{task_id}/create-branch."""

    def test_creates_branch_successfully(self, client, test_task):
        with patch(
            "devboard.services.task_git_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = test_task.branch_name

            response = client.post(f"/api/tasks/{test_task.id}/create-branch")

        assert response.status_code == 200
        data = response.json()
        assert data == {
            "success": True,
            "message": f"Branch {test_task.branch_name} created successfully",
        }
        mock_create.assert_called_once()

    def test_returns_404_for_invalid_task(self, client):
        response = client.post("/api/tasks/9999/create-branch")
        assert response.status_code == 404

    def test_returns_400_on_git_failure(self, client, test_task):
        with patch(
            "devboard.services.task_git_service.TaskGitService.create_task_branch",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.side_effect = ValueError("git error")

            response = client.post(f"/api/tasks/{test_task.id}/create-branch")

        assert response.status_code == 400
        assert "git error" in response.json()["detail"]
