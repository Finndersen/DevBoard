"""Tests for AgentConfigService."""

from unittest.mock import Mock

import pytest

from devboard.agents.agent_config_service import AgentConfigService
from devboard.agents.config_types import AgentEngineModelInput
from devboard.agents.engines import AgentEngine, agent_engine_registry
from devboard.agents.language_models import ModelType, llm_registry
from devboard.agents.roles import AgentRoleType
from devboard.config.base import ConfigValidationResult


class TestAgentConfigService:
    """Tests for AgentConfigService."""

    @pytest.fixture
    def agent_config_service(self, agent_role_config_repository, config_service):
        """Create AgentConfigService instance for testing."""
        return AgentConfigService(
            agent_role_config_repo=agent_role_config_repository,
            config_service=config_service,
            llm_registry=llm_registry,
            engine_registry=agent_engine_registry,
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

        # Should include all Anthropic models from LLMRegistry
        expected_claude_models = [
            "anthropic:claude-sonnet-4.5",
            "anthropic:claude-opus-4.1",
            "anthropic:claude-opus-4",
            "anthropic:claude-sonnet-4",
            "anthropic:claude-haiku-4-5",
        ]
        assert set(claude_model_ids) == set(expected_claude_models)

        # Test Gemini CLI - should return ALL Google models
        gemini_models = agent_config_service._get_available_models_for_engine(AgentEngine.GEMINI_CLI)
        gemini_model_ids = [m.id for m in gemini_models]

        # Should include all Google models from LLMRegistry (including gemini-2.5-flash-lite)
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
        # PROJECT role recommends REASONING models (INTERNAL engine requires selection)
        project_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRoleType.PROJECT, AgentEngine.INTERNAL
        )
        # Should return a valid model ID in provider:model format
        assert ":" in project_default
        # Verify it's a REASONING model
        model = agent_config_service._llm_registry.get(project_default)
        assert model is not None
        assert model.type == ModelType.REASONING

        # INVESTIGATION role recommends FAST models (INTERNAL engine requires selection)
        investigation_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRoleType.INVESTIGATION, AgentEngine.INTERNAL
        )
        # Should return a valid model ID in provider:model format
        assert ":" in investigation_default
        # Verify it's a FAST model
        model = agent_config_service._llm_registry.get(investigation_default)
        assert model is not None
        assert model.type == ModelType.FAST

    def test_update_agent_configuration_validates_model(self, agent_config_service):
        """update_agent_configuration should validate model is available for engine."""
        # Should allow valid Anthropic model for Claude Code
        config = AgentEngineModelInput(
            engine=AgentEngine.CLAUDE_CODE,
            model_id="anthropic:claude-sonnet-4.5",
        )
        result = agent_config_service.update_agent_configuration(AgentRoleType.TASK_IMPLEMENTATION, config)
        assert result.config.model_id == "anthropic:claude-sonnet-4.5"

        # Should reject model from unsupported provider for engine
        config = AgentEngineModelInput(
            engine=AgentEngine.CLAUDE_CODE,
            model_id="google:gemini-2.5-pro",  # Google model for Anthropic-only engine
        )
        with pytest.raises(ValueError, match="not available for engine"):
            agent_config_service.update_agent_configuration(AgentRoleType.TASK_IMPLEMENTATION, config)

    def test_get_agent_configuration_returns_effective_config(self, agent_config_service):
        """get_agent_configuration should return effective engine and model config."""
        # Test PROJECT role (INTERNAL engine)
        project_config = agent_config_service.get_agent_configuration(AgentRoleType.PROJECT)
        assert project_config.agent_role == "project"
        assert project_config.config.engine is not None
        assert project_config.config.model_id is not None
        assert len(project_config.available_engines) > 0

        # PROJECT should allow INTERNAL and CLAUDE_CODE engines
        assert len(project_config.available_engines) == 2
        engine_names = {e.engine for e in project_config.available_engines}
        assert engine_names == {"internal", "claude_code"}

        # Test TASK_IMPLEMENTATION role (Claude Code by default)
        task_impl_config = agent_config_service.get_agent_configuration(AgentRoleType.TASK_IMPLEMENTATION)
        assert task_impl_config.agent_role == "task_implementation"

        # TASK_IMPLEMENTATION should allow multiple engines
        assert len(task_impl_config.available_engines) == 2
        engine_names = {e.engine for e in task_impl_config.available_engines}
        assert engine_names == {"claude_code", "gemini_cli"}

    def test_language_model_full_name(self):
        """LanguageModel should have optional full_name attribute."""
        # Test Anthropic models have full_name
        claude_sonnet = llm_registry.get("anthropic:claude-sonnet-4.5")
        assert claude_sonnet is not None
        assert claude_sonnet.full_name == "claude-sonnet-4-5-20250929"
        assert claude_sonnet.display_full_name == "claude-sonnet-4-5-20250929"

        # Test models without full_name default to name
        gpt5 = llm_registry.get("openai:gpt-5")
        assert gpt5 is not None
        assert gpt5.full_name is None
        assert gpt5.display_full_name == "gpt-5"

    def test_default_model_for_engines_not_requiring_selection(self, agent_config_service):
        """Engines that don't require model selection should return None as default."""
        # Claude Code doesn't require model selection
        claude_code_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRoleType.TASK_IMPLEMENTATION, AgentEngine.CLAUDE_CODE
        )
        assert claude_code_default is None

        # Gemini CLI doesn't require model selection
        gemini_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRoleType.TASK_IMPLEMENTATION, AgentEngine.GEMINI_CLI
        )
        assert gemini_default is None

        # INTERNAL engine requires model selection, should return a model ID
        internal_default = agent_config_service._get_default_model_for_agent_role_and_engine(
            AgentRoleType.PROJECT, AgentEngine.INTERNAL
        )
        assert internal_default is not None
        assert ":" in internal_default

    def test_update_config_with_none_model_for_claude_code(self, agent_config_service):
        """Update configuration with None model_id for Claude Code should succeed."""
        config = AgentEngineModelInput(
            engine=AgentEngine.CLAUDE_CODE,
            model_id=None,
        )
        result = agent_config_service.update_agent_configuration(AgentRoleType.TASK_IMPLEMENTATION, config)
        assert result.config.engine == AgentEngine.CLAUDE_CODE
        assert result.config.model_id is None

    def test_update_config_with_none_model_for_internal_fails(self, agent_config_service):
        """Update configuration with None model_id for INTERNAL should fail validation."""
        config = AgentEngineModelInput(
            engine=AgentEngine.INTERNAL,
            model_id=None,
        )
        with pytest.raises(ValueError, match="requires explicit model selection"):
            agent_config_service.update_agent_configuration(AgentRoleType.PROJECT, config)

    def test_engine_info_includes_requires_model_selection(self, agent_config_service):
        """Engine info should include requires_model_selection field."""
        # Get configuration for a role that supports multiple engines
        config = agent_config_service.get_agent_configuration(AgentRoleType.TASK_IMPLEMENTATION)

        # Check that engines have the requires_model_selection field
        for engine_info in config.available_engines:
            assert hasattr(engine_info, "requires_model_selection")
            if engine_info.engine == "claude_code" or engine_info.engine == "gemini_cli":
                assert engine_info.requires_model_selection is False
            elif engine_info.engine == "internal":
                assert engine_info.requires_model_selection is True

    def test_get_effective_config_returns_none_for_claude_code_default(self, agent_config_service):
        """get_effective_config should return None model_id for Claude Code when not explicitly set."""
        # Set engine to Claude Code without selecting a model
        config = AgentEngineModelInput(
            engine=AgentEngine.CLAUDE_CODE,
            model_id=None,
        )
        agent_config_service.update_agent_configuration(AgentRoleType.TASK_IMPLEMENTATION, config)

        # Get effective config should return None model and model_id
        effective_config = agent_config_service.get_effective_config(AgentRoleType.TASK_IMPLEMENTATION)
        assert effective_config.engine == AgentEngine.CLAUDE_CODE
        assert effective_config.model is None
        assert effective_config.model_id is None

    def test_check_engine_availability_internal_with_configured_providers(self, agent_config_service):
        """INTERNAL engine should be available when LLM providers are configured."""
        is_available, reason = agent_config_service._check_engine_availability(AgentEngine.INTERNAL)
        # In test environment, Anthropic is typically configured
        assert is_available is True
        assert reason is None

    def test_check_engine_availability_external_engines_always_available(self, agent_config_service):
        """External engines (CLAUDE_CODE, GEMINI_CLI) should always be available."""
        is_available, reason = agent_config_service._check_engine_availability(AgentEngine.CLAUDE_CODE)
        assert is_available is True
        assert reason is None

        is_available, reason = agent_config_service._check_engine_availability(AgentEngine.GEMINI_CLI)
        assert is_available is True
        assert reason is None

    def test_engine_info_includes_availability_fields(self, agent_config_service):
        """Engine info should include is_available and unavailable_reason fields."""
        config = agent_config_service.get_agent_configuration(AgentRoleType.TASK_IMPLEMENTATION)

        for engine_info in config.available_engines:
            assert hasattr(engine_info, "is_available")
            assert hasattr(engine_info, "unavailable_reason")
            # External engines should always be available
            if engine_info.engine in ("claude_code", "gemini_cli"):
                assert engine_info.is_available is True
                assert engine_info.unavailable_reason is None

    def test_check_engine_availability_internal_without_providers(self, agent_role_config_repository):
        """INTERNAL engine should be unavailable when no LLM providers are configured."""
        mock_config_service = Mock()
        # All provider validation calls return failure (no providers configured)
        mock_config_service.validate_config_by_key.return_value = ConfigValidationResult(
            success=False,
            config=None,
            errors=["API key not configured"],
        )

        service = AgentConfigService(
            agent_role_config_repo=agent_role_config_repository,
            config_service=mock_config_service,
            llm_registry=llm_registry,
            engine_registry=agent_engine_registry,
        )

        is_available, reason = service._check_engine_availability(AgentEngine.INTERNAL)
        assert is_available is False
        assert reason is not None
        assert "No LLM providers configured" in reason
