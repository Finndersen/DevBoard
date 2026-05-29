"""Tests for agents API endpoints."""


class TestAgentsRouter:
    """Tests for /api/agents endpoints."""

    def test_get_agent_configuration(self, client):
        """GET /agents/{agent_role}/configuration should return config."""
        # Test PROJECT role
        response = client.get("/api/agents/project/configuration")
        assert response.status_code == 200

        data = response.json()
        assert data["agent_role"] == "project"
        assert "config" in data
        assert "engine" in data["config"]
        assert "model" in data["config"]
        assert "available_engines" in data
        assert len(data["available_engines"]) > 0
        assert "enabled_mcp_tools" in data
        assert data["enabled_mcp_tools"] == []  # Empty by default

        # All engines should be available for all roles
        assert len(data["available_engines"]) == 3
        engine_names = {e["engine"] for e in data["available_engines"]}
        assert engine_names == {"internal", "claude_code", "gemini_cli"}

    def test_get_agent_configuration_task_implementation(self, client):
        """TASK_IMPLEMENTATION should allow multiple engines."""
        response = client.get("/api/agents/task_implementation/configuration")
        assert response.status_code == 200

        data = response.json()
        assert data["agent_role"] == "task_implementation"

        # All engines should be available for all roles
        assert len(data["available_engines"]) == 3
        engine_names = {e["engine"] for e in data["available_engines"]}
        assert engine_names == {"internal", "claude_code", "gemini_cli"}

    def test_get_agent_configuration_invalid_role(self, client):
        """Invalid agent role should return 400."""
        response = client.get("/api/agents/invalid_role/configuration")
        assert response.status_code == 400
        assert "Invalid agent role" in response.json()["detail"]

    def test_update_agent_configuration(self, client):
        """PUT /agents/{agent_role}/configuration should update config."""
        # Update TASK_IMPLEMENTATION to use Claude Code with specific model
        response = client.put(
            "/api/agents/task_implementation/configuration",
            json={
                "engine": "claude_code",
                "model_id": "anthropic:claude-sonnet-4.5",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["agent_role"] == "task_implementation"
        assert data["config"]["engine"] == "claude_code"
        assert data["config"]["model"]["id"] == "anthropic:claude-sonnet-4.5"

        # Verify configuration persisted
        response = client.get("/api/agents/task_implementation/configuration")
        assert response.status_code == 200
        data = response.json()
        assert data["config"]["engine"] == "claude_code"
        assert data["config"]["model"]["id"] == "anthropic:claude-sonnet-4.5"

    def test_update_agent_configuration_with_specific_model(self, client):
        """Update configuration with specific model ID."""
        response = client.put(
            "/api/agents/task_implementation/configuration",
            json={
                "engine": "claude_code",
                "model_id": "anthropic:claude-sonnet-4.5",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["config"]["engine"] == "claude_code"
        assert data["config"]["model"]["id"] == "anthropic:claude-sonnet-4.5"

    def test_update_agent_configuration_invalid_engine_for_role(self, client):
        """All engines should be allowed for all roles."""
        # Use Gemini CLI for PROJECT role (previously restricted, now allowed)
        response = client.put(
            "/api/agents/project/configuration",
            json={
                "engine": "gemini_cli",
                "model_id": None,
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["agent_role"] == "project"
        assert data["config"]["engine"] == "gemini_cli"

    def test_update_agent_configuration_rejects_wrong_provider_for_engine(self, client):
        """Should reject model from unsupported provider for engine."""
        # Try to use Google model with Claude Code (which only supports Anthropic)
        response = client.put(
            "/api/agents/task_implementation/configuration",
            json={
                "engine": "claude_code",
                "model_id": "google:gemini-2.5-pro",
            },
        )
        assert response.status_code == 400
        assert "not available for engine" in response.json()["detail"]

    def test_update_agent_configuration_invalid_model(self, client):
        """Should reject invalid model ID."""
        response = client.put(
            "/api/agents/task_implementation/configuration",
            json={
                "engine": "claude_code",
                "model_id": "invalid:model",
            },
        )
        assert response.status_code == 400
        assert "not available" in response.json()["detail"]

    def test_get_available_models_by_engine(self, client):
        """GET /agents/available-models should return models by engine based on supported providers."""
        response = client.get("/api/agents/available-models")
        assert response.status_code == 200

        data = response.json()
        assert "models_by_engine" in data

        # Check INTERNAL engine - has models from all configured providers
        assert "internal" in data["models_by_engine"]
        internal_models = data["models_by_engine"]["internal"]
        internal_model_ids = [m["id"] for m in internal_models]
        # Should have provider:model format
        assert all(":" in m_id for m_id in internal_model_ids)

        # Check CLAUDE_CODE engine - only Anthropic models
        assert "claude_code" in data["models_by_engine"]
        claude_models = data["models_by_engine"]["claude_code"]
        claude_model_ids = [m["id"] for m in claude_models]
        # Should only have Anthropic models
        assert all(m_id.startswith("anthropic:") for m_id in claude_model_ids)
        # Verify key Anthropic models are present
        assert "anthropic:claude-sonnet-4.5" in claude_model_ids
        assert "anthropic:claude-opus-4.1" in claude_model_ids

        # Check GEMINI_CLI engine - only Google models
        assert "gemini_cli" in data["models_by_engine"]
        gemini_models = data["models_by_engine"]["gemini_cli"]
        gemini_model_ids = [m["id"] for m in gemini_models]
        # Should only have Google models
        assert all(m_id.startswith("google:") for m_id in gemini_model_ids)
        # Verify key Google models are present
        assert "google:gemini-2.5-pro" in gemini_model_ids
        assert "google:gemini-2.5-flash" in gemini_model_ids

    def test_get_available_mcp_tools_empty(self, client):
        """GET /agents/available-mcp-tools returns empty list when no verified servers exist."""
        response = client.get("/api/agents/available-mcp-tools")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_agent_role_tools_empty(self, client):
        """GET /agents/{role}/tools returns empty list by default."""
        response = client.get("/api/agents/project/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "project"
        assert data["tools"] == []

    def test_update_agent_configuration_with_custom_instructions(self, client):
        """PUT /agents/{role}/configuration can set custom instructions."""
        response = client.put(
            "/api/agents/project/configuration",
            json={
                "engine": "internal",
                "model_id": "openai:gpt-4.1",
                "custom_instructions": "Always be helpful and concise.",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["custom_instructions"] == "Always be helpful and concise."

        # Verify persisted
        response = client.get("/api/agents/project/configuration")
        assert response.status_code == 200
        data = response.json()
        assert data["custom_instructions"] == "Always be helpful and concise."

    def test_update_agent_configuration_clear_custom_instructions(self, client):
        """Setting custom_instructions to null clears them."""
        # First set instructions
        client.put(
            "/api/agents/project/configuration",
            json={
                "engine": "internal",
                "model_id": "openai:gpt-4.1",
                "custom_instructions": "Some instructions",
            },
        )

        # Then clear them
        response = client.put(
            "/api/agents/project/configuration",
            json={
                "engine": "internal",
                "model_id": "openai:gpt-4.1",
                "custom_instructions": None,
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert data["custom_instructions"] is None
