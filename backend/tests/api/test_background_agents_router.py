"""Tests for background agents and background agent runs API endpoints."""

import pytest


@pytest.fixture
def agent_payload() -> dict:
    """Base payload for creating a background agent."""
    return {
        "name": "Test Agent",
        "prompt": "You are a helpful test agent.",
        "engine": "internal",
    }


@pytest.fixture
def created_agent(client, agent_payload) -> dict:
    """Create a background agent and return its response data."""
    resp = client.post("/api/background-agents/", json=agent_payload)
    assert resp.status_code == 201
    return resp.json()


class TestCreateBackgroundAgent:
    """POST /api/background-agents/ — create a new background agent."""

    def test_create_minimal(self, client, agent_payload):
        resp = client.post("/api/background-agents/", json=agent_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Agent"
        assert data["prompt"] == "You are a helpful test agent."
        assert data["engine"] == "internal"
        assert data["enabled"] is True
        assert data["description"] is None
        assert data["model_id"] is None
        assert data["project_id"] is None
        assert data["mcp_tool_ids"] == []
        assert data["event_triggers"] == []
        assert data["schedule_triggers"] == []
        assert "id" in data
        assert "state" in data

    def test_create_with_description_and_model(self, client):
        resp = client.post(
            "/api/background-agents/",
            json={
                "name": "Full Agent",
                "prompt": "Act as a full-featured agent.",
                "engine": "internal",
                "description": "A complete agent",
                "model_id": "openai:gpt-4.1",
                "enabled": False,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "A complete agent"
        assert data["model_id"] == "openai:gpt-4.1"
        assert data["enabled"] is False

    def test_create_with_event_triggers(self, client):
        resp = client.post(
            "/api/background-agents/",
            json={
                "name": "Triggered Agent",
                "prompt": "Handle events.",
                "engine": "internal",
                "event_triggers": [
                    {"event_type_pattern": "task.created"},
                    {"event_type_pattern": "task.updated"},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["event_triggers"]) == 2
        patterns = {t["event_type_pattern"] for t in data["event_triggers"]}
        assert patterns == {"task.created", "task.updated"}

    def test_create_with_schedule_triggers(self, client):
        resp = client.post(
            "/api/background-agents/",
            json={
                "name": "Scheduled Agent",
                "prompt": "Run on schedule.",
                "engine": "internal",
                "schedule_triggers": [{"cron_expression": "0 9 * * *"}],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["schedule_triggers"]) == 1
        assert data["schedule_triggers"][0]["cron_expression"] == "0 9 * * *"


class TestListBackgroundAgents:
    """GET /api/background-agents/ — list background agents."""

    def test_list_empty(self, client):
        resp = client.get("/api/background-agents/")
        assert resp.status_code == 200
        # May have other agents from other tests; just check it's a list
        assert isinstance(resp.json(), list)

    def test_list_includes_created_agent(self, client, created_agent):
        resp = client.get("/api/background-agents/")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert created_agent["id"] in ids

    def test_list_filter_enabled_true(self, client):
        # Create enabled and disabled agents
        client.post(
            "/api/background-agents/", json={"name": "Enabled", "prompt": "p", "engine": "internal", "enabled": True}
        )
        client.post(
            "/api/background-agents/", json={"name": "Disabled", "prompt": "p", "engine": "internal", "enabled": False}
        )

        resp = client.get("/api/background-agents/?enabled=true")
        assert resp.status_code == 200
        for agent in resp.json():
            assert agent["enabled"] is True

    def test_list_filter_enabled_false(self, client):
        client.post(
            "/api/background-agents/",
            json={"name": "Disabled2", "prompt": "p", "engine": "internal", "enabled": False},
        )

        resp = client.get("/api/background-agents/?enabled=false")
        assert resp.status_code == 200
        for agent in resp.json():
            assert agent["enabled"] is False


class TestGetBackgroundAgent:
    """GET /api/background-agents/{agent_id} — get agent details."""

    def test_get_existing(self, client, created_agent):
        agent_id = created_agent["id"]
        resp = client.get(f"/api/background-agents/{agent_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == agent_id
        assert data["name"] == created_agent["name"]

    def test_get_not_found(self, client):
        resp = client.get("/api/background-agents/999999")
        assert resp.status_code == 404


class TestUpdateBackgroundAgent:
    """PUT /api/background-agents/{agent_id} — update agent configuration."""

    def test_update_name_and_prompt(self, client, created_agent):
        agent_id = created_agent["id"]
        resp = client.put(
            f"/api/background-agents/{agent_id}",
            json={
                "name": "Updated Name",
                "prompt": "Updated prompt.",
                "engine": "internal",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["prompt"] == "Updated prompt."

    def test_update_replaces_triggers(self, client):
        # Create with event triggers
        resp = client.post(
            "/api/background-agents/",
            json={
                "name": "Trigger Replace Agent",
                "prompt": "p",
                "engine": "internal",
                "event_triggers": [{"event_type_pattern": "old.event"}],
            },
        )
        agent_id = resp.json()["id"]

        # Update with new triggers
        resp = client.put(
            f"/api/background-agents/{agent_id}",
            json={
                "name": "Trigger Replace Agent",
                "prompt": "p",
                "engine": "internal",
                "event_triggers": [{"event_type_pattern": "new.event"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["event_triggers"]) == 1
        assert data["event_triggers"][0]["event_type_pattern"] == "new.event"

    def test_update_not_found(self, client):
        resp = client.put("/api/background-agents/999999", json={"name": "x", "prompt": "p", "engine": "internal"})
        assert resp.status_code == 404


class TestUpdateBackgroundAgentState:
    """PATCH /api/background-agents/{agent_id}/state — partial state merge."""

    def test_state_patch_merges(self, client, created_agent):
        agent_id = created_agent["id"]
        resp = client.patch(f"/api/background-agents/{agent_id}/state", json={"state": {"key1": "value1"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"]["key1"] == "value1"

        # Merge additional key
        resp = client.patch(f"/api/background-agents/{agent_id}/state", json={"state": {"key2": "value2"}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"]["key1"] == "value1"
        assert data["state"]["key2"] == "value2"

    def test_state_patch_not_found(self, client):
        resp = client.patch("/api/background-agents/999999/state", json={"state": {"k": "v"}})
        assert resp.status_code == 404


class TestDeleteBackgroundAgent:
    """DELETE /api/background-agents/{agent_id} — delete agent."""

    def test_delete_existing(self, client, agent_payload):
        # Create then delete
        create_resp = client.post("/api/background-agents/", json=agent_payload)
        agent_id = create_resp.json()["id"]

        resp = client.delete(f"/api/background-agents/{agent_id}")
        assert resp.status_code == 204

        # Verify gone
        get_resp = client.get(f"/api/background-agents/{agent_id}")
        assert get_resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/background-agents/999999")
        assert resp.status_code == 404


class TestManualTrigger:
    """POST /api/background-agents/{agent_id}/trigger — manual trigger placeholder."""

    def test_trigger_returns_conversation_id(self, client, created_agent):
        agent_id = created_agent["id"]
        resp = client.post(f"/api/background-agents/{agent_id}/trigger")
        assert resp.status_code == 201
        data = resp.json()
        assert "conversation_id" in data
        assert isinstance(data["conversation_id"], int)

    def test_trigger_not_found(self, client):
        resp = client.post("/api/background-agents/999999/trigger")
        assert resp.status_code == 404


class TestListBackgroundAgentRuns:
    """GET /api/background-agents/{agent_id}/runs — list runs for an agent."""

    def test_list_runs_empty(self, client, created_agent):
        agent_id = created_agent["id"]
        resp = client.get(f"/api/background-agents/{agent_id}/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_runs_not_found(self, client):
        resp = client.get("/api/background-agents/999999/runs")
        assert resp.status_code == 404


class TestBackgroundAgentRunStats:
    """GET /api/background-agents/{agent_id}/runs/stats — aggregate stats."""

    def test_stats_no_runs(self, client, created_agent):
        agent_id = created_agent["id"]
        resp = client.get(f"/api/background-agents/{agent_id}/runs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0
        assert data["avg_input_tokens"] is None
        assert data["avg_output_tokens"] is None

    def test_stats_agent_not_found(self, client):
        resp = client.get("/api/background-agents/999999/runs/stats")
        assert resp.status_code == 404
