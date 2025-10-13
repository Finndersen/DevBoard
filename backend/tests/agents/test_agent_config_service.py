"""Tests for AgentConfigService."""

import pytest

from devboard.agents.agent_config_service import AgentConfigService, AgentEngineModelConfig
from devboard.agents.engines.agent_engines import AgentEngine
from devboard.agents.language_models import ModelType
from devboard.agents.roles.types import AgentRole


class TestAgentConfigService:
    """Tests for AgentConfigService."""

    @pytest.fixture
    def agent_config_service(self, config_service):
        """Create AgentConfigService instance for testing."""
        from devboard.agents.engines.agent_engines import default_agent_engine_repository
        from devboard.agents.language_models import default_llm_repository

        return AgentConfigService(
            config_service=config_service,
            llm_repository=default_llm_repository,
            engine_repository=default_agent_engine_repository,
        )

    def test_internal_engine_filters_by_api_configuration(self, agent_config_service):
        """INTERNAL engine should only return models from configured providers."""
        models = agent_config_service._get_available_models_for_engine(AgentEngine.INTERNAL)
        model_ids = [m.id for m in models]

        # Should only include models from providers with API keys configured
        # In test environment, typically only Anthropic is configured via env vars
        assert all(":" in model_id for model_id in model_ids), "All models should have provider:model format"

        # Models should be filtered by configured providers
        # (exact models depend on which providers are configured in test env)
        print(f"INTERNAL engine models: {model_ids}")

    def test_external_engines_return_all_models(self, agent_config_service):
        """External engines should return all models from their supported providers without API key filtering."""
        # Test Claude Code - should return ALL Anthropic models
        claude_models = agent_config_service._get_available_models_for_engine(AgentEngine.CLAUDE_CODE)
        claude_model_ids = [m.id for m in claude_models]

        # Should include all Anthropic models from LLMRepository
        expected_claude_models = [
            "anthropic:claude-sonnet-4.5",
            "anthropic:claude-opus-4.1",
            "anthropic:claude-opus-4",
            "anthropic:claude-sonnet-4",
            "anthropic:claude-sonnet-3.7",
            "anthropic:claude-haiku-3.5",
        ]
        assert set(claude_model_ids) == set(expected_claude_models)

        # Test Gemini CLI - should return ALL Google models
        gemini_models = agent_config_service._get_available_models_for_engine(AgentEngine.GEMINI_CLI)
        gemini_model_ids = [m.id for m in gemini_models]

        # Should include all Google models from LLMRepository (including gemini-2.5-flash-lite)
        assert "google:gemini-2.5-pro" in gemini_model_ids
        assert "google:gemini-2.5-flash" in gemini_model_ids
        assert "google:gemini-2.5-flash-lite" in gemini_model_ids
        # All returned models should be from Google provider
        assert all(m_id.startswith("google:") for m_id in gemini_model_ids)

    def test_get_available_models_by_engine_returns_provider_models(self, agent_config_service):
        """get_available_models_by_engine should return models based on engine's supported providers."""
        result = agent_config_service.get_available_models_by_engine()

        # Check INTERNAL engine has models from configured providers
        internal_models = result.models_by_engine["internal"]
        internal_model_ids = [m.id for m in internal_models]
        # Should have provider:model format, no "default"
        assert all(":" in m_id for m_id in internal_model_ids)

        # Check CLAUDE_CODE engine has Anthropic models
        claude_models = result.models_by_engine["claude_code"]
        claude_model_ids = [m.id for m in claude_models]
        # Should only have Anthropic models
        assert all(m_id.startswith("anthropic:") for m_id in claude_model_ids)
        # Should include key Anthropic models
        assert "anthropic:claude-sonnet-4.5" in claude_model_ids
        assert "anthropic:claude-opus-4.1" in claude_model_ids

        # Check GEMINI_CLI engine has Google models
        gemini_models = result.models_by_engine["gemini_cli"]
        gemini_model_ids = [m.id for m in gemini_models]
        # Should only have Google models
        assert all(m_id.startswith("google:") for m_id in gemini_model_ids)
        # Should include key Google models
        assert "google:gemini-2.5-pro" in gemini_model_ids
        assert "google:gemini-2.5-flash" in gemini_model_ids

    def test_get_default_model_for_agent_role(self, agent_config_service):
        """_get_default_model_for_agent_role should select model based on agent role's recommended type."""
        # PROJECT role recommends REASONING models
        project_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRole.PROJECT, AgentEngine.INTERNAL
        )
        # Should return a valid model ID in provider:model format
        assert ":" in project_default
        # Verify it's a REASONING model
        model = agent_config_service.llm_repository.get_model_by_id(project_default)

        assert model.type == ModelType.REASONING

        # INVESTIGATION role recommends FAST models
        investigation_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRole.INVESTIGATION, AgentEngine.INTERNAL
        )
        # Should return a valid model ID in provider:model format
        assert ":" in investigation_default
        # Verify it's a FAST model
        model = agent_config_service.llm_repository.get_model_by_id(investigation_default)
        assert model.type == ModelType.FAST

        # External engines should also work and select by recommended type
        task_impl_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRole.TASK_IMPLEMENTATION, AgentEngine.CLAUDE_CODE
        )
        # Should return an Anthropic model (Claude Code only supports Anthropic)
        assert task_impl_default.startswith("anthropic:")
        # Should be a REASONING model (recommended for TASK_IMPLEMENTATION)
        model = agent_config_service.llm_repository.get_model_by_id(task_impl_default)
        assert model.type == ModelType.REASONING

    def test_update_agent_configuration_validates_model(self, agent_config_service):
        """update_agent_configuration should validate model is available for engine."""
        # Should allow valid Anthropic model for Claude Code
        config = AgentEngineModelConfig(
            engine=AgentEngine.CLAUDE_CODE,
            model_id="anthropic:claude-sonnet-4.5",
        )
        result = agent_config_service.update_agent_configuration(AgentRole.TASK_IMPLEMENTATION, config)
        assert result.config.model_id == "anthropic:claude-sonnet-4.5"

        # Should reject model from unsupported provider for engine
        config = AgentEngineModelConfig(
            engine=AgentEngine.CLAUDE_CODE,
            model_id="google:gemini-2.5-pro",  # Google model for Anthropic-only engine
        )
        with pytest.raises(ValueError, match="not available for engine"):
            agent_config_service.update_agent_configuration(AgentRole.TASK_IMPLEMENTATION, config)

    def test_get_agent_configuration_returns_effective_config(self, agent_config_service):
        """get_agent_configuration should return effective engine and model config."""
        # Test PROJECT role (INTERNAL engine)
        project_config = agent_config_service.get_agent_configuration(AgentRole.PROJECT)
        assert project_config.agent_role == "project"
        assert project_config.config.engine is not None
        assert project_config.config.model_id is not None
        assert len(project_config.available_engines) > 0

        # PROJECT should only allow INTERNAL engine
        assert len(project_config.available_engines) == 1
        assert project_config.available_engines[0].engine == "internal"

        # Test TASK_IMPLEMENTATION role (Claude Code by default)
        task_impl_config = agent_config_service.get_agent_configuration(AgentRole.TASK_IMPLEMENTATION)
        assert task_impl_config.agent_role == "task_implementation"

        # TASK_IMPLEMENTATION should allow multiple engines
        assert len(task_impl_config.available_engines) == 2
        engine_names = {e.engine for e in task_impl_config.available_engines}
        assert engine_names == {"claude_code", "gemini_cli"}

    def test_language_model_full_name(self):
        """LanguageModel should have optional full_name attribute."""
        from devboard.agents.language_models import default_llm_repository

        # Test Anthropic models have full_name
        claude_sonnet = default_llm_repository.get_model_by_id("anthropic:claude-sonnet-4.5")
        assert claude_sonnet.full_name == "claude-sonnet-4-5-20250929"
        assert claude_sonnet.display_full_name == "claude-sonnet-4-5-20250929"

        # Test models without full_name default to name
        gpt5 = default_llm_repository.get_model_by_id("openai:gpt-5")
        assert gpt5.full_name is None
        assert gpt5.display_full_name == "gpt-5"
