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
