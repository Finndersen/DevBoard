"""Tests for TaskImplementationPlanService timing/timestamp behaviour."""

import pytest

from devboard.db.models.implementation_plan import ImplementationStepStatus
from devboard.db.repositories.implementation_plan import TaskImplementationPlanRepository
from devboard.services.task_implementation_plan import TaskImplementationPlanService


class TestAddStepNumbering:
    """Regression tests for duplicate step number bug.

    When add_step is called multiple times within the same SQLAlchemy session,
    the in-memory plan.steps relationship may be stale, causing both calls to
    compute the same new step number. The fix queries max step_number from the
    DB directly.
    """

    @pytest.fixture
    def plan_repo(self, db_session):
        return TaskImplementationPlanRepository(db_session)

    @pytest.fixture
    def plan_service(self, plan_repo):
        return TaskImplementationPlanService(plan_repo)

    @pytest.fixture
    def plan(self, test_task, plan_repo, db_session):
        plan = plan_repo.create(task_id=test_task.id, overview=None)
        plan_repo.create_steps(
            plan.id,
            [{"title": "Step 1", "type": "code_change", "dependencies": [], "details": "Initial step"}],
        )
        db_session.flush()
        return plan

    def test_add_step_twice_produces_unique_step_numbers(self, plan_service, plan):
        step_a = plan_service.add_step(plan, title="Step A", type="code_change", details="A")
        step_b = plan_service.add_step(plan, title="Step B", type="code_change", details="B")

        assert step_a.step_number != step_b.step_number
        assert sorted([step_a.step_number, step_b.step_number]) == [2, 3]


class TestSetStepStatusTimestamps:
    @pytest.fixture
    def plan_repo(self, db_session):
        return TaskImplementationPlanRepository(db_session)

    @pytest.fixture
    def plan_service(self, plan_repo):
        return TaskImplementationPlanService(plan_repo)

    @pytest.fixture
    def plan_with_step(self, test_task, plan_repo, db_session):
        plan = plan_repo.create(task_id=test_task.id, overview=None)
        plan_repo.create_steps(
            plan.id,
            [{"title": "Step 1", "type": "code_change", "dependencies": [], "details": "Do the thing"}],
        )
        db_session.flush()
        return plan

    @pytest.fixture
    def step_one(self, plan_with_step):
        return plan_with_step.steps[0]

    def test_running_sets_started_at(self, plan_service, step_one):
        step = plan_service.set_step_status(step_one, ImplementationStepStatus.RUNNING)

        assert step.started_at is not None
        assert step.completed_at is None

    def test_complete_sets_completed_at(self, plan_service, step_one):
        plan_service.set_step_status(step_one, ImplementationStepStatus.RUNNING)
        step = plan_service.set_step_status(step_one, ImplementationStepStatus.COMPLETE)

        assert step.started_at is not None
        assert step.completed_at is not None

    def test_failed_sets_completed_at(self, plan_service, step_one):
        plan_service.set_step_status(step_one, ImplementationStepStatus.RUNNING)
        step = plan_service.set_step_status(step_one, ImplementationStepStatus.FAILED)

        assert step.started_at is not None
        assert step.completed_at is not None

    def test_skipped_sets_completed_at(self, plan_service, step_one):
        step = plan_service.set_step_status(step_one, ImplementationStepStatus.SKIPPED)

        assert step.completed_at is not None

    def test_pending_does_not_set_timestamps(self, plan_service, step_one):
        step = plan_service.set_step_status(step_one, ImplementationStepStatus.PENDING)

        assert step.started_at is None
        assert step.completed_at is None

    def test_running_after_failed_resets_started_at(self, plan_service, step_one):
        plan_service.set_step_status(step_one, ImplementationStepStatus.RUNNING)
        step_after_first_run = plan_service.set_step_status(step_one, ImplementationStepStatus.FAILED)
        original_started_at = step_after_first_run.started_at

        step = plan_service.set_step_status(step_one, ImplementationStepStatus.RUNNING)

        assert step.started_at is not None
        assert step.started_at != original_started_at
