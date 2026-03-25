"""Test language models API endpoints."""

import pytest

from devboard.agents.language_models import LLMProvider, ModelType
from devboard.db.repositories.language_model import LanguageModelRepository


@pytest.fixture
def language_model_repo(db_session):
    """LanguageModelRepository instance for testing."""
    return LanguageModelRepository(db_session)


@pytest.fixture
def sample_model(language_model_repo, db_session):
    """Create a sample language model for testing."""
    model = language_model_repo.create(
        provider=LLMProvider.ANTHROPIC,
        name="claude-test-model",
        model_type=ModelType.STANDARD,
        full_name="claude-test-model-20250101",
        bedrock_id=None,
    )
    db_session.commit()
    return model


class TestListLanguageModels:
    def test_list_returns_seeded_models(self, client):
        response = client.get("/api/language-models/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert all("id" in m and "provider" in m and "name" in m for m in data)

    def test_list_with_models(self, client, sample_model):
        response = client.get("/api/language-models/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        ids = [m["id"] for m in data]
        assert sample_model.id in ids


class TestCreateLanguageModel:
    def test_create_success(self, client):
        payload = {
            "provider": "openai",
            "name": "gpt-new-model",
            "model_type": "standard",
            "full_name": None,
            "bedrock_id": None,
        }
        response = client.post("/api/language-models/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "openai"
        assert data["name"] == "gpt-new-model"
        assert data["model_type"] == "standard"
        assert data["model_id"] == "openai:gpt-new-model"
        assert "id" in data

    def test_create_with_optional_fields(self, client):
        payload = {
            "provider": "anthropic",
            "name": "claude-optional-test",
            "model_type": "advanced",
            "full_name": "claude-optional-test-20250101",
            "bedrock_id": "eu.anthropic.claude-optional-test-v1:0",
        }
        response = client.post("/api/language-models/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "claude-optional-test-20250101"
        assert data["bedrock_id"] == "eu.anthropic.claude-optional-test-v1:0"

    def test_create_duplicate_returns_409(self, client, sample_model):
        payload = {
            "provider": sample_model.provider.value,
            "name": sample_model.name,
            "model_type": "fast",
        }
        response = client.post("/api/language-models/", json=payload)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_create_invalid_provider_returns_422(self, client):
        payload = {
            "provider": "invalid-provider",
            "name": "some-model",
            "model_type": "standard",
        }
        response = client.post("/api/language-models/", json=payload)
        assert response.status_code == 422

    def test_create_invalid_model_type_returns_422(self, client):
        payload = {
            "provider": "openai",
            "name": "some-model",
            "model_type": "invalid-type",
        }
        response = client.post("/api/language-models/", json=payload)
        assert response.status_code == 422


class TestUpdateLanguageModel:
    def test_update_name(self, client, sample_model):
        payload = {"name": "claude-renamed-model"}
        response = client.put(f"/api/language-models/{sample_model.id}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "claude-renamed-model"
        assert data["provider"] == sample_model.provider.value

    def test_update_model_type(self, client, sample_model):
        payload = {"model_type": "fast"}
        response = client.put(f"/api/language-models/{sample_model.id}", json=payload)
        assert response.status_code == 200
        assert response.json()["model_type"] == "fast"

    def test_update_not_found_returns_404(self, client):
        response = client.put("/api/language-models/99999", json={"name": "new-name"})
        assert response.status_code == 404

    def test_update_duplicate_provider_name_returns_409(self, client, sample_model, language_model_repo, db_session):
        # Create a second model to conflict with
        language_model_repo.create(
            provider=LLMProvider.OPENAI,
            name="gpt-conflict-target",
            model_type=ModelType.FAST,
        )
        db_session.commit()

        # Try to rename sample_model to same provider+name as other
        payload = {"provider": "openai", "name": "gpt-conflict-target"}
        response = client.put(f"/api/language-models/{sample_model.id}", json=payload)
        assert response.status_code == 409


class TestDeleteLanguageModel:
    def test_delete_success(self, client, language_model_repo, db_session):
        model = language_model_repo.create(
            provider=LLMProvider.GOOGLE,
            name="gemini-to-delete",
            model_type=ModelType.FAST,
        )
        db_session.commit()

        response = client.delete(f"/api/language-models/{model.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_delete_not_found_returns_404(self, client):
        response = client.delete("/api/language-models/99999")
        assert response.status_code == 404
