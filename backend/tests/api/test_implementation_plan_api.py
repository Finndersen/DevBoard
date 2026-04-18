import pytest
from fastapi.testclient import TestClient

from devboard.db.repositories.implementation_plan import TaskImplementationPlanRepository


class TestImplementationPlanAPI:
    @pytest.fixture
    def plan_repo(self, db_session):
        return TaskImplementationPlanRepository(db_session)

    @pytest.fixture
    def task_with_plan(self, test_task, plan_repo, db_session):
        plan = plan_repo.create(task_id=test_task.id, overview="Test overview")
        plan_repo.create_steps(
            plan.id,
            [
                {
                    "title": "Set up models",
                    "type": "code_change",
                    "dependencies": [],
                    "details": "Create the DB models",
                },
                {"title": "Add tests", "type": "validation", "dependencies": [1], "details": "Write tests for models"},
            ],
        )
        db_session.flush()
        return test_task

    def test_get_implementation_plan(self, client: TestClient, task_with_plan):
        response = client.get(f"/api/tasks/{task_with_plan.id}/implementation-plan")
        assert response.status_code == 200

        data = response.json()
        assert data["task_id"] == task_with_plan.id
        assert data["overview"] == "Test overview"
        assert data["status"] == "pending"
        assert len(data["steps"]) == 2

        step1 = data["steps"][0]
        assert step1["step_number"] == 1
        assert step1["title"] == "Set up models"
        assert step1["type"] == "code_change"
        assert step1["dependencies"] == []
        assert step1["status"] == "pending"
        assert step1["details"] == "Create the DB models"
        assert step1["outcome"] is None
        assert step1["started_at"] is None
        assert step1["completed_at"] is None

        step2 = data["steps"][1]
        assert step2["step_number"] == 2
        assert step2["title"] == "Add tests"
        assert step2["dependencies"] == [1]

    def test_get_implementation_plan_not_found(self, client: TestClient, test_task):
        response = client.get(f"/api/tasks/{test_task.id}/implementation-plan")
        assert response.status_code == 404

    def test_get_implementation_plan_task_not_found(self, client: TestClient):
        response = client.get("/api/tasks/99999/implementation-plan")
        assert response.status_code == 404

    def test_update_implementation_step(self, client: TestClient, task_with_plan):
        response = client.patch(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps/1",
            json={"title": "Updated title", "details": "Updated details"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == "Updated title"
        assert data["details"] == "Updated details"
        assert data["step_number"] == 1

    def test_update_implementation_step_partial(self, client: TestClient, task_with_plan):
        response = client.patch(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps/1",
            json={"title": "Only title changed"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == "Only title changed"
        assert data["details"] == "Create the DB models"  # unchanged

    def test_update_implementation_step_not_found(self, client: TestClient, task_with_plan):
        response = client.patch(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps/99",
            json={"title": "Test"},
        )
        assert response.status_code == 404

    def test_task_response_includes_implementation_plan_id(self, client: TestClient, task_with_plan, plan_repo):
        response = client.get(f"/api/tasks/{task_with_plan.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["implementation_plan_id"] is not None

        # Verify it matches the plan ID
        plan = plan_repo.get_by_task_id(task_with_plan.id)
        assert plan is not None
        assert data["implementation_plan_id"] == plan.id

    def test_task_response_no_plan(self, client: TestClient, test_task):
        response = client.get(f"/api/tasks/{test_task.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["implementation_plan_id"] is None

    def test_create_implementation_step(self, client: TestClient, task_with_plan):
        response = client.post(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps",
            json={"title": "Code review", "type": "code_review", "details": "Review the git diff.", "dependencies": []},
        )
        assert response.status_code == 201

        data = response.json()
        assert data["title"] == "Code review"
        assert data["type"] == "code_review"
        assert data["details"] == "Review the git diff."
        assert data["dependencies"] == []
        assert data["step_number"] == 3
        assert data["status"] == "pending"

    def test_create_implementation_step_with_dependencies(self, client: TestClient, task_with_plan):
        response = client.post(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps",
            json={
                "title": "Code review",
                "type": "code_review",
                "details": "Review the git diff.",
                "dependencies": [1, 2],
            },
        )
        assert response.status_code == 201

        data = response.json()
        assert data["dependencies"] == [1, 2]
        assert data["step_number"] == 3

    def test_create_implementation_step_no_plan(self, client: TestClient, test_task):
        response = client.post(
            f"/api/tasks/{test_task.id}/implementation-plan/steps",
            json={"title": "Code review", "type": "code_review", "details": "Review the git diff."},
        )
        assert response.status_code == 404

    def test_create_implementation_step_invalid_dependency(self, client: TestClient, task_with_plan):
        response = client.post(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps",
            json={"title": "Code review", "type": "code_review", "details": "Review.", "dependencies": [99]},
        )
        assert response.status_code == 400

    def test_get_implementation_plan_includes_model_fields(self, client: TestClient, task_with_plan):
        response = client.get(f"/api/tasks/{task_with_plan.id}/implementation-plan")
        assert response.status_code == 200

        data = response.json()
        step = data["steps"][0]
        assert "model_type" in step
        assert "model_display_name" in step
        assert step["model_type"] is None
        assert step["model_display_name"] is None

    def test_create_implementation_step_with_model_type(self, client: TestClient, task_with_plan):
        response = client.post(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps",
            json={
                "title": "Code review",
                "type": "code_review",
                "details": "Review the git diff.",
                "model_type": "standard",
            },
        )
        assert response.status_code == 201

        data = response.json()
        assert data["model_type"] == "standard"
        # CODE_REVIEW role → INTERNAL engine → OpenAI models (only configured provider in tests)
        assert data["model_display_name"] == "gpt-5"

    def test_create_implementation_step_fast_model_type(self, client: TestClient, task_with_plan):
        response = client.post(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps",
            json={
                "title": "Run tests",
                "type": "validation",
                "details": "Run the test suite.",
                "model_type": "fast",
            },
        )
        assert response.status_code == 201

        data = response.json()
        assert data["model_type"] == "fast"
        # STEP_EXECUTION role → CLAUDE_CODE engine → Anthropic models
        assert data["model_display_name"] == "claude-haiku-4-5"

    def test_update_implementation_step_model_type(self, client: TestClient, task_with_plan):
        response = client.patch(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps/1",
            json={"model_type": "advanced"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["model_type"] == "advanced"
        # STEP_EXECUTION role → CLAUDE_CODE engine → Anthropic models
        assert data["model_display_name"].startswith("claude-opus")

    def test_plan_step_model_type_persisted_after_create(self, client: TestClient, task_with_plan):
        client.post(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps",
            json={"title": "New step", "type": "validation", "details": "Validate.", "model_type": "fast"},
        )
        response = client.get(f"/api/tasks/{task_with_plan.id}/implementation-plan")
        assert response.status_code == 200

        steps = response.json()["steps"]
        new_step = next(s for s in steps if s["title"] == "New step")
        assert new_step["model_type"] == "fast"
        assert new_step["model_display_name"] == "claude-haiku-4-5"

    def test_create_implementation_step_invalid_model_type(self, client: TestClient, task_with_plan):
        response = client.post(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps",
            json={"title": "Some step", "type": "validation", "details": "Do it.", "model_type": "invalid"},
        )
        assert response.status_code == 400

    def test_update_implementation_step_invalid_model_type(self, client: TestClient, task_with_plan):
        response = client.patch(
            f"/api/tasks/{task_with_plan.id}/implementation-plan/steps/1",
            json={"model_type": "invalid"},
        )
        assert response.status_code == 400
