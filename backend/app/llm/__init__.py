"""Pick the LLM provider named in settings."""

from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMProvider


def get_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings.llm_model, settings.llm_effort, settings.anthropic_api_key)
    from app.llm.mock_provider import MockProvider

    return MockProvider()
