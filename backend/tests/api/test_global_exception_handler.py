"""Tests for the global ValueError exception handler in main.py."""

from unittest.mock import AsyncMock, patch


class TestGlobalValueErrorHandler:
    """The global ValueError handler converts unhandled ValueErrors to HTTP 400."""

    def test_unhandled_value_error_returns_400(self, client, test_task):
        """A ValueError that escapes an endpoint becomes a 400 with the detail message."""
        # Patch create_task_branch so it raises ValueError — the tasks router's
        # own try/except converts this to HTTPException(400), so use the projects
        # endpoint (create_project_task) which has no per-endpoint handler.
        with patch(
            "devboard.api.routers.projects.TaskService.create_task",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.side_effect = ValueError("Codebase path does not exist: /tmp/no-such-dir")

            response = client.post(
                f"/api/projects/{test_task.project_id}/tasks",
                json={
                    "title": "Test task",
                    "codebase_id": test_task.codebase_id,
                },
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "Codebase path does not exist: /tmp/no-such-dir"
