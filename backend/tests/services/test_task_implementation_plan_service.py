"""Tests for TaskImplementationPlanService timing/timestamp behaviour."""

import pytest

from devboard.db.models.implementation_plan import ImplementationStepStatus
from devboard.db.repositories.implementation_plan import TaskImplementationPlanRepository
from devboard.services.task_implementation_plan import TaskImplementationPlanService


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

    def test_running_sets_started_at(self, plan_service, plan_with_step):
        step = plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.RUNNING)

        assert step.started_at is not None
        assert step.completed_at is None

    def test_complete_sets_completed_at(self, plan_service, plan_with_step):
        plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.RUNNING)
        step = plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.COMPLETE)

        assert step.started_at is not None
        assert step.completed_at is not None

    def test_failed_sets_completed_at(self, plan_service, plan_with_step):
        plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.RUNNING)
        step = plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.FAILED)

        assert step.started_at is not None
        assert step.completed_at is not None

    def test_skipped_sets_completed_at(self, plan_service, plan_with_step):
        step = plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.SKIPPED)

        assert step.completed_at is not None

    def test_pending_does_not_set_timestamps(self, plan_service, plan_with_step):
        step = plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.PENDING)

        assert step.started_at is None
        assert step.completed_at is None

    def test_running_after_failed_resets_started_at(self, plan_service, plan_with_step):
        plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.RUNNING)
        step_after_first_run = plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.FAILED)
        original_started_at = step_after_first_run.started_at

        step = plan_service.set_step_status(plan_with_step, 1, ImplementationStepStatus.RUNNING)

        assert step.started_at is not None
        assert step.started_at != original_started_at
