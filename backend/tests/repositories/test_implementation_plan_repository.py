import pytest
from sqlalchemy.orm import Session

from devboard.agents.language_models import ModelType
from devboard.db.models import Codebase, Project
from devboard.db.models.document import DocumentType
from devboard.db.models.implementation_plan import (
    ImplementationStep,
    ImplementationStepStatus,
    ImplementationStepType,
)
from devboard.db.repositories import CodebaseRepository, DocumentRepository, TaskRepository
from devboard.db.repositories.implementation_plan import TaskImplementationPlanRepository
from devboard.db.repositories.project import ProjectRepository
from devboard.services.task_implementation_plan import TaskImplementationPlanService


class TestTaskImplementationPlanRepository:
    @pytest.fixture
    def repo(self, db_session: Session) -> TaskImplementationPlanRepository:
        return TaskImplementationPlanRepository(db_session)

    @pytest.fixture
    def codebase(self, db_session: Session) -> Codebase:
        codebase_repo = CodebaseRepository(db_session)
        codebase = Codebase(
            name="Test Codebase",
            description="A test codebase",
            local_path="/tmp/test-codebase",
        )
        codebase = codebase_repo.create(codebase)
        db_session.flush()
        return codebase

    @pytest.fixture
    def project(self, db_session: Session, document_repository: DocumentRepository) -> Project:
        project_repo = ProjectRepository(db_session)
        spec_doc = document_repository.create(DocumentType.PROJECT_SPECIFICATION, "")
        project = project_repo.create(name="Test Project", description="", specification=spec_doc)
        db_session.flush()
        return project

    @pytest.fixture
    def task(self, db_session: Session, project: Project, codebase: Codebase, document_repository: DocumentRepository):
        task_repo = TaskRepository(db_session)
        spec_doc = document_repository.create(DocumentType.TASK_SPECIFICATION, "Test spec")
        task = task_repo.create(
            project_id=project.id,
            title="Test Task",
            specification=spec_doc,
            base_branch="main",
            branch_name="feature/test-task",
            codebase_id=codebase.id,
        )
        db_session.flush()
        return task

    def test_create_plan(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id, overview="Test overview")
        db_session.flush()

        assert plan.id is not None
        assert plan.task_id == task.id
        assert plan.overview == "Test overview"
        assert plan.status == "pending"

    def test_create_plan_default_status(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        db_session.flush()

        assert plan.status == "pending"
        assert plan.overview is None

    def test_get_by_task_id(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        repo.create(task_id=task.id, overview="Test")
        db_session.flush()

        found = repo.get_by_task_id(task.id)
        assert found is not None
        assert found.task_id == task.id
        assert found.overview == "Test"

    def test_get_by_task_id_not_found(self, repo: TaskImplementationPlanRepository):
        assert repo.get_by_task_id(99999) is None

    def test_get_by_id(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        db_session.flush()

        found = repo.get_by_id(plan.id)
        assert found is not None
        assert found.id == plan.id

    def test_delete_by_task_id(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        repo.create(task_id=task.id)
        db_session.flush()

        repo.delete_by_task_id(task.id)
        db_session.flush()

        assert repo.get_by_task_id(task.id) is None

    def test_delete_by_task_id_nonexistent(self, repo: TaskImplementationPlanRepository):
        # Should not raise
        repo.delete_by_task_id(99999)

    def test_create_steps_bulk(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        db_session.flush()

        steps_data = [
            {"title": "Step 1", "type": "code_change", "dependencies": [], "details": "Do step 1"},
            {"title": "Step 2", "type": "validation", "dependencies": [1], "details": "Do step 2"},
            {"title": "Step 3", "type": "documentation", "dependencies": [1, 2], "details": "Do step 3"},
        ]

        steps = repo.create_steps(plan.id, steps_data)
        db_session.flush()

        assert len(steps) == 3
        assert steps[0].step_number == 1
        assert steps[0].title == "Step 1"
        assert steps[0].type == ImplementationStepType.CODE_CHANGE
        assert steps[0].status == ImplementationStepStatus.PENDING
        assert steps[1].step_number == 2
        assert steps[1].dependencies == [1]
        assert steps[2].step_number == 3
        assert steps[2].type == ImplementationStepType.DOCUMENTATION

    def test_create_steps_with_model_type(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        db_session.flush()

        steps_data = [
            {"title": "Fast step", "type": "validation", "details": "Run tests", "model_type": "fast"},
            {"title": "Standard step", "type": "code_change", "details": "Write code", "model_type": "standard"},
            {"title": "No model step", "type": "documentation", "details": "Write docs"},
        ]

        steps = repo.create_steps(plan.id, steps_data)
        db_session.flush()

        assert steps[0].model_type == ModelType.FAST
        assert steps[1].model_type == ModelType.STANDARD
        assert steps[2].model_type is None

    def test_get_step_by_number(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        repo.create_steps(plan.id, [{"title": "Step 1", "type": "code_change", "details": "Details"}])
        db_session.flush()

        step = repo.get_step_by_number(plan.id, 1)
        assert step is not None
        assert step.title == "Step 1"

        assert repo.get_step_by_number(plan.id, 99) is None

    def test_update_step(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        repo.create_steps(plan.id, [{"title": "Original", "type": "code_change", "details": "Details"}])
        db_session.flush()

        step = repo.get_step_by_number(plan.id, 1)
        assert step is not None
        step.title = "Updated"
        step.status = ImplementationStepStatus.COMPLETE
        step.outcome = "Done successfully"
        repo.update_step(step)
        db_session.flush()

        updated = repo.get_step_by_number(plan.id, 1)
        assert updated is not None
        assert updated.title == "Updated"
        assert updated.status == ImplementationStepStatus.COMPLETE
        assert updated.outcome == "Done successfully"

    def test_delete_step_no_dependents(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        repo.create_steps(
            plan.id,
            [
                {"title": "Step 1", "type": "code_change", "details": "Details"},
                {"title": "Step 2", "type": "validation", "dependencies": [1], "details": "Details"},
            ],
        )
        db_session.flush()

        # Refetch plan to get steps
        plan = repo.get_by_task_id(task.id)
        assert plan is not None
        step2 = repo.get_step_by_number(plan.id, 2)
        assert step2 is not None
        repo.delete_step(step2, plan)
        db_session.flush()

        assert repo.get_step_by_number(plan.id, 2) is None

    def test_delete_step_with_dependents_raises(
        self, repo: TaskImplementationPlanRepository, task, db_session: Session
    ):
        plan = repo.create(task_id=task.id)
        repo.create_steps(
            plan.id,
            [
                {"title": "Step 1", "type": "code_change", "details": "Details"},
                {"title": "Step 2", "type": "validation", "dependencies": [1], "details": "Details"},
            ],
        )
        db_session.flush()

        plan = repo.get_by_task_id(task.id)
        assert plan is not None
        step1 = repo.get_step_by_number(plan.id, 1)
        assert step1 is not None

        with pytest.raises(ValueError, match="step 2 depends on it"):
            repo.delete_step(step1, plan)

    def test_plan_replacement(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        # Create initial plan
        plan1 = repo.create(task_id=task.id, overview="Plan 1")
        repo.create_steps(plan1.id, [{"title": "Old Step", "type": "code_change", "details": "Old details"}])
        db_session.flush()

        # Delete and create new plan
        repo.delete_by_task_id(task.id)
        plan2 = repo.create(task_id=task.id, overview="Plan 2")
        repo.create_steps(plan2.id, [{"title": "New Step", "type": "validation", "details": "New details"}])
        db_session.flush()

        found = repo.get_by_task_id(task.id)
        assert found is not None
        assert found.overview == "Plan 2"
        assert len(found.steps) == 1
        assert found.steps[0].title == "New Step"

    def test_cascade_delete_steps(self, repo: TaskImplementationPlanRepository, task, db_session: Session):
        plan = repo.create(task_id=task.id)
        steps = repo.create_steps(
            plan.id,
            [
                {"title": "Step 1", "type": "code_change", "details": "Details 1"},
                {"title": "Step 2", "type": "validation", "details": "Details 2"},
            ],
        )
        db_session.flush()
        step_ids = [s.id for s in steps]

        repo.delete_by_task_id(task.id)
        db_session.flush()

        # Verify steps are also deleted
        for step_id in step_ids:
            result = db_session.get(ImplementationStep, step_id)
            assert result is None


class TestDependencyGraphValidation:
    def test_valid_linear_graph(self):
        steps = [
            {"dependencies": []},
            {"dependencies": [1]},
            {"dependencies": [2]},
        ]
        TaskImplementationPlanService.validate_dependency_graph(steps)

    def test_valid_diamond_graph(self):
        steps = [
            {"dependencies": []},
            {"dependencies": [1]},
            {"dependencies": [1]},
            {"dependencies": [2, 3]},
        ]
        TaskImplementationPlanService.validate_dependency_graph(steps)

    def test_valid_no_dependencies(self):
        steps = [
            {"dependencies": []},
            {"dependencies": []},
            {"dependencies": []},
        ]
        TaskImplementationPlanService.validate_dependency_graph(steps)

    def test_cycle_detection(self):
        steps = [
            {"dependencies": [2]},
            {"dependencies": [1]},
        ]
        with pytest.raises(ValueError, match="cycle"):
            TaskImplementationPlanService.validate_dependency_graph(steps)

    def test_self_dependency(self):
        steps = [
            {"dependencies": [1]},
        ]
        with pytest.raises(ValueError, match="cannot depend on itself"):
            TaskImplementationPlanService.validate_dependency_graph(steps)

    def test_invalid_reference(self):
        steps = [
            {"dependencies": [5]},
        ]
        with pytest.raises(ValueError, match="non-existent step 5"):
            TaskImplementationPlanService.validate_dependency_graph(steps)

    def test_three_node_cycle(self):
        steps = [
            {"dependencies": [3]},
            {"dependencies": [1]},
            {"dependencies": [2]},
        ]
        with pytest.raises(ValueError, match="cycle"):
            TaskImplementationPlanService.validate_dependency_graph(steps)
