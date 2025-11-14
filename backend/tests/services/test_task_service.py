"""Tests for TaskService state transition methods."""

from unittest.mock import MagicMock

import pytest

from devboard.db.models.document import DocumentType
from devboard.db.models.task import Task, TaskStatus
from devboard.services.task_service import TaskService


@pytest.fixture
def mock_conversation_service():
    """Mock ConversationService."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_document_repo():
    """Mock DocumentRepository."""
    repo = MagicMock()

    # Mock document creation
    def create_document(doc_type, content):
        doc = MagicMock()
        doc.id = 999
        doc.document_type = doc_type
        doc.content = content
        return doc

    repo.create.side_effect = create_document
    return repo


@pytest.fixture
def mock_task_repo():
    """Mock TaskRepository."""
    repo = MagicMock()
    repo.update.side_effect = lambda task: task  # Return the task as-is
    return repo


@pytest.fixture
def task_service(mock_conversation_service, mock_document_repo, mock_task_repo):
    """Create TaskService instance with mocked dependencies."""
    return TaskService(
        conversation_service=mock_conversation_service,
        document_repo=mock_document_repo,
        task_repo=mock_task_repo,
    )


@pytest.fixture
def task_in_defining():
    """Create a task in DEFINING state with specification content."""
    task = MagicMock(spec=Task)
    task.id = 1
    task.status = TaskStatus.DEFINING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = None
    task.implementation_plan_id = None
    # Mock can_transition_to_phase to return success by default
    task.can_transition_to_phase.return_value = (True, "")
    return task


@pytest.fixture
def task_in_defining_empty_spec():
    """Create a task in DEFINING state with empty specification."""
    task = MagicMock(spec=Task)
    task.id = 2
    task.status = TaskStatus.DEFINING
    task.specification = MagicMock()
    task.specification.content = ""
    task.implementation_plan = None
    task.implementation_plan_id = None
    return task


@pytest.fixture
def task_in_planning():
    """Create a task in PLANNING state with implementation plan content."""
    task = MagicMock(spec=Task)
    task.id = 3
    task.status = TaskStatus.PLANNING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = MagicMock()
    task.implementation_plan.content = "# Implementation Plan\n\nTest plan"
    # Mock can_transition_to_phase to return success by default
    task.can_transition_to_phase.return_value = (True, "")
    return task


@pytest.fixture
def task_in_planning_empty_plan():
    """Create a task in PLANNING state with empty implementation plan."""
    task = MagicMock(spec=Task)
    task.id = 4
    task.status = TaskStatus.PLANNING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = MagicMock()
    task.implementation_plan.content = ""
    return task


@pytest.fixture
def task_in_implementing():
    """Create a task in IMPLEMENTING state."""
    task = MagicMock(spec=Task)
    task.id = 5
    task.status = TaskStatus.IMPLEMENTING
    task.specification = MagicMock()
    task.specification.content = "# Task Specification\n\nTest content"
    task.implementation_plan = MagicMock()
    task.implementation_plan.content = "# Implementation Plan\n\nTest plan"
    return task


class TestTransitionToPlanning:
    """Tests for TaskService.transition_to_planning()."""

    def test_successful_transition(self, task_service, task_in_defining, mock_document_repo, mock_task_repo):
        """Test successful transition from DEFINING to PLANNING."""
        # Execute transition
        result = task_service.transition_to_planning(task_in_defining)

        # Verify implementation_plan document was created
        mock_document_repo.create.assert_called_once_with(DocumentType.TASK_IMPLEMENTATION_PLAN, "")

        # Verify task status was updated
        assert task_in_defining.status == TaskStatus.PLANNING

        # Verify implementation_plan was assigned
        assert task_in_defining.implementation_plan_id == 999

        # Verify task was updated in repository
        mock_task_repo.update.assert_called_once_with(task_in_defining)

        # Verify result is the updated task
        assert result == task_in_defining

    def test_transition_with_existing_plan(self, task_service, task_in_defining, mock_document_repo, mock_task_repo):
        """Test transition when implementation_plan already exists."""
        # Setup: Task already has a plan
        task_in_defining.implementation_plan = MagicMock()
        task_in_defining.implementation_plan.id = 100
        task_in_defining.implementation_plan_id = 100

        # Execute transition
        task_service.transition_to_planning(task_in_defining)

        # Verify implementation_plan document was NOT created (already exists)
        mock_document_repo.create.assert_not_called()

        # Verify task status was updated
        assert task_in_defining.status == TaskStatus.PLANNING

        # Verify task was updated in repository
        mock_task_repo.update.assert_called_once_with(task_in_defining)

    def test_transition_wrong_status(self, task_service, task_in_planning):
        """Test transition fails when task is not in DEFINING status."""
        with pytest.raises(ValueError, match="must be in DEFINING status"):
            task_service.transition_to_planning(task_in_planning)

    def test_transition_empty_specification(self, task_service, task_in_defining_empty_spec):
        """Test transition fails when specification is empty."""
        # Mock can_transition_to_phase to return False
        task_in_defining_empty_spec.can_transition_to_phase.return_value = (
            False,
            "Cannot transition to PLANNING without specification content",
        )

        with pytest.raises(ValueError, match="specification content"):
            task_service.transition_to_planning(task_in_defining_empty_spec)


class TestTransitionToImplementing:
    """Tests for TaskService.transition_to_implementing()."""

    def test_successful_transition(self, task_service, task_in_planning, mock_task_repo):
        """Test successful transition from PLANNING to IMPLEMENTING."""
        # Execute transition
        result = task_service.transition_to_implementing(task_in_planning)

        # Verify task status was updated
        assert task_in_planning.status == TaskStatus.IMPLEMENTING

        # Verify task was updated in repository
        mock_task_repo.update.assert_called_once_with(task_in_planning)

        # Verify result is the updated task
        assert result == task_in_planning

    def test_transition_wrong_status(self, task_service, task_in_defining):
        """Test transition fails when task is not in PLANNING status."""
        with pytest.raises(ValueError, match="must be in PLANNING status"):
            task_service.transition_to_implementing(task_in_defining)

    def test_transition_empty_plan(self, task_service, task_in_planning_empty_plan):
        """Test transition fails when implementation plan is empty."""
        # Mock can_transition_to_phase to return False
        task_in_planning_empty_plan.can_transition_to_phase.return_value = (
            False,
            "Cannot transition to IMPLEMENTING without implementation plan",
        )

        with pytest.raises(ValueError, match="implementation plan"):
            task_service.transition_to_implementing(task_in_planning_empty_plan)

    def test_transition_from_implementing_fails(self, task_service, task_in_implementing):
        """Test transition fails when task is already in IMPLEMENTING status."""
        with pytest.raises(ValueError, match="must be in PLANNING status"):
            task_service.transition_to_implementing(task_in_implementing)


class TestTransitionValidation:
    """Tests for validation logic in transition methods."""

    def test_planning_transition_validates_status_before_prerequisites(
        self, task_service, task_in_planning, mock_document_repo
    ):
        """Test that status check happens before prerequisite validation."""
        # Task is in PLANNING (wrong status), but has empty spec
        task_in_planning.specification.content = ""
        task_in_planning.can_transition_to_phase.return_value = (
            False,
            "Cannot transition to PLANNING without specification content",
        )

        # Should fail with status error, not prerequisite error
        with pytest.raises(ValueError, match="must be in DEFINING status"):
            task_service.transition_to_planning(task_in_planning)

        # Verify can_transition_to_phase was never called (status check failed first)
        task_in_planning.can_transition_to_phase.assert_not_called()

    def test_implementing_transition_validates_status_before_prerequisites(
        self, task_service, task_in_defining, mock_task_repo
    ):
        """Test that status check happens before prerequisite validation."""
        # Task is in DEFINING (wrong status), but has empty plan
        task_in_defining.implementation_plan = MagicMock()
        task_in_defining.implementation_plan.content = ""
        task_in_defining.can_transition_to_phase.return_value = (
            False,
            "Cannot transition to IMPLEMENTING without implementation plan",
        )

        # Should fail with status error, not prerequisite error
        with pytest.raises(ValueError, match="must be in PLANNING status"):
            task_service.transition_to_implementing(task_in_defining)

        # Verify can_transition_to_phase was never called (status check failed first)
        task_in_defining.can_transition_to_phase.assert_not_called()
