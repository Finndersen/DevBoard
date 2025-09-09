"""Tests for conversation models including BaseConversationMessage inheritance."""

import datetime

from sqlalchemy.orm import Session

from devboard.db.models import Project, ProjectConversationMessage, Task, TaskConversationMessage
from devboard.db.repositories import ProjectRepository, TaskRepository


class TestProjectConversationMessage:
    """Test ProjectConversationMessage model inheriting from BaseConversationMessage."""

    def test_project_conversation_message_creation(self, db_session: Session):
        """Test creating a ProjectConversationMessage."""
        # Create a project first
        project_repo = ProjectRepository(db_session)
        project = Project(
            name="Test Project",
            details="Test project details",
            current_status="active"
        )
        created_project = project_repo.create(project)
        db_session.commit()

        # Create a project conversation message
        message = ProjectConversationMessage(
            project_id=created_project.id,
            role="user",
            content="What is the current status of this project?"
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify the message was created with inherited fields
        assert message.id is not None
        assert message.project_id == created_project.id
        assert message.role == "user"
        assert message.content == "What is the current status of this project?"
        assert message.tool_data is None
        assert isinstance(message.created_at, datetime.datetime)

    def test_project_conversation_message_with_tool_data(self, db_session: Session):
        """Test ProjectConversationMessage with tool data."""
        # Create a project first
        project_repo = ProjectRepository(db_session)
        project = Project(
            name="Test Project",
            details="Test project details",
            current_status="active"
        )
        created_project = project_repo.create(project)
        db_session.commit()

        # Create message with tool data
        tool_data = {
            "tool_name": "get_relevant_context",
            "resource_uri": "https://github.com/org/repo",
            "query": "recent commits",
            "result": "Found 5 recent commits..."
        }

        message = ProjectConversationMessage(
            project_id=created_project.id,
            role="tool_result",
            content=None,
            tool_data=tool_data
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify tool data is stored correctly
        assert message.role == "tool_result"
        assert message.content is None
        assert message.tool_data == tool_data
        assert message.tool_data["tool_name"] == "get_relevant_context"

    def test_project_conversation_message_relationship(self, db_session: Session):
        """Test the relationship between Project and ProjectConversationMessage."""
        # Create project with messages
        project_repo = ProjectRepository(db_session)
        project = Project(
            name="Test Project",
            details="Test project details",
            current_status="active"
        )
        created_project = project_repo.create(project)
        db_session.commit()

        # Add multiple messages
        messages_data = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
            {"role": "user", "content": "Second message"}
        ]

        for msg_data in messages_data:
            message = ProjectConversationMessage(
                project_id=created_project.id,
                **msg_data
            )
            db_session.add(message)

        db_session.commit()
        db_session.refresh(created_project)

        # Test relationship works
        assert len(created_project.messages) == 3
        assert all(msg.project_id == created_project.id for msg in created_project.messages)

        # Test back reference
        first_message = created_project.messages[0]
        assert first_message.project.id == created_project.id


class TestTaskConversationMessage:
    """Test TaskConversationMessage model inheriting from BaseConversationMessage."""

    def test_task_conversation_message_creation(self, db_session: Session):
        """Test creating a TaskConversationMessage."""
        # Create a task first (need project too)
        project_repo = ProjectRepository(db_session)
        project = Project(
            name="Test Project",
            details="Test project details",
            current_status="active"
        )
        created_project = project_repo.create(project)
        db_session.commit()

        task_repo = TaskRepository(db_session)
        task = Task(
            title="Test Task",
            description="Test task description",
            status="Designing",
            project_id=created_project.id
        )
        created_task = task_repo.create(task)
        db_session.commit()

        # Create task conversation message
        message = TaskConversationMessage(
            task_id=created_task.id,
            role="user",
            content="Please help me design this task specification."
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify message creation with inherited fields
        assert message.id is not None
        assert message.task_id == created_task.id
        assert message.role == "user"
        assert message.content == "Please help me design this task specification."
        assert message.tool_data is None
        assert isinstance(message.created_at, datetime.datetime)

    def test_task_conversation_message_agent_response(self, db_session: Session):
        """Test TaskConversationMessage storing agent response with edits."""
        # Create task
        project_repo = ProjectRepository(db_session)
        project = Project(name="Test Project", details="Details", current_status="active")
        created_project = project_repo.create(project)
        db_session.commit()

        task_repo = TaskRepository(db_session)
        task = Task(
            title="Test Task",
            description="Description",
            status="Planning",
            project_id=created_project.id
        )
        created_task = task_repo.create(task)
        db_session.commit()

        # Agent response with new structured format
        agent_response_data = {
            "task_specification_edits": [
                {"find": "old objective", "replace": "new objective"},
                {"find": "TODO", "replace": "Implement authentication"}
            ],
            "task_implementation_plan_edits": [
                {"find": "[Step 1]", "replace": "Set up OAuth configuration"}
            ]
        }

        message = TaskConversationMessage(
            task_id=created_task.id,
            role="assistant",
            content="I've updated both the specification and implementation plan based on your requirements.",
            tool_data=agent_response_data
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Verify structured agent response storage
        assert message.role == "assistant"
        assert "updated both the specification and implementation plan" in message.content
        assert message.tool_data is not None
        assert "task_specification_edits" in message.tool_data
        assert "task_implementation_plan_edits" in message.tool_data
        assert len(message.tool_data["task_specification_edits"]) == 2
        assert len(message.tool_data["task_implementation_plan_edits"]) == 1

    def test_task_conversation_message_relationship(self, db_session: Session):
        """Test the relationship between Task and TaskConversationMessage."""
        # Create task with conversation
        project_repo = ProjectRepository(db_session)
        project = Project(name="Test Project", details="Details", current_status="active")
        created_project = project_repo.create(project)
        db_session.commit()

        task_repo = TaskRepository(db_session)
        task = Task(
            title="Test Task",
            description="Description",
            status="Designing",
            project_id=created_project.id
        )
        created_task = task_repo.create(task)
        db_session.commit()

        # Add conversation messages
        conversation = [
            {"role": "user", "content": "Start designing this task"},
            {"role": "assistant", "content": "I'll help you create a task specification",
             "tool_data": {"task_specification_edits": []}},
            {"role": "user", "content": "Can you add more detail?"}
        ]

        for msg_data in conversation:
            message = TaskConversationMessage(
                task_id=created_task.id,
                **msg_data
            )
            db_session.add(message)

        db_session.commit()
        db_session.refresh(created_task)

        # Test relationship
        assert len(created_task.messages) == 3
        assert all(msg.task_id == created_task.id for msg in created_task.messages)

        # Test back reference
        first_message = created_task.messages[0]
        assert first_message.task.id == created_task.id

    def test_conversation_message_roles(self, db_session: Session):
        """Test different conversation message roles."""
        # Create project and task
        project_repo = ProjectRepository(db_session)
        project = Project(name="Test Project", details="Details", current_status="active")
        created_project = project_repo.create(project)
        db_session.commit()

        task_repo = TaskRepository(db_session)
        task = Task(title="Test Task", description="Desc", status="Planning", project_id=created_project.id)
        created_task = task_repo.create(task)
        db_session.commit()

        # Test all supported roles
        roles_and_data = [
            ("user", "User message", None),
            ("assistant", "Agent response", None),
            ("tool_call", None, {"tool": "get_relevant_context", "args": {"uri": "test", "query": "test"}}),
            ("tool_result", None, {"result": "Context retrieved successfully"})
        ]

        for role, content, tool_data in roles_and_data:
            message = TaskConversationMessage(
                task_id=created_task.id,
                role=role,
                content=content,
                tool_data=tool_data
            )
            db_session.add(message)

        db_session.commit()
        db_session.refresh(created_task)

        # Verify all roles were stored correctly
        assert len(created_task.messages) == 4
        stored_roles = [msg.role for msg in created_task.messages]
        assert "user" in stored_roles
        assert "assistant" in stored_roles
        assert "tool_call" in stored_roles
        assert "tool_result" in stored_roles

    def test_conversation_message_timestamps(self, db_session: Session):
        """Test that timestamps are automatically set and ordered."""
        # Create project and task
        project_repo = ProjectRepository(db_session)
        project = Project(name="Test Project", details="Details", current_status="active")
        created_project = project_repo.create(project)
        db_session.commit()

        task_repo = TaskRepository(db_session)
        task = Task(title="Test Task", description="Desc", status="Designing", project_id=created_project.id)
        created_task = task_repo.create(task)
        db_session.commit()

        # Create messages with slight delay
        import time

        message1 = TaskConversationMessage(
            task_id=created_task.id,
            role="user",
            content="First message"
        )
        db_session.add(message1)
        db_session.commit()

        time.sleep(0.01)  # Small delay

        message2 = TaskConversationMessage(
            task_id=created_task.id,
            role="assistant",
            content="Second message"
        )
        db_session.add(message2)
        db_session.commit()

        db_session.refresh(message1)
        db_session.refresh(message2)

        # Verify timestamps
        assert message1.created_at < message2.created_at
        assert isinstance(message1.created_at, datetime.datetime)
        assert isinstance(message2.created_at, datetime.datetime)
