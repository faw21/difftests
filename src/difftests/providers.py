"""LLM provider abstraction for difftests."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str: ...


class ClaudeProvider(LLMProvider):
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, model: str | None = None) -> None:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Run: export ANTHROPIC_API_KEY=your-key"
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def complete(self, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text


class OpenAIProvider(LLMProvider):
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, model: str | None = None) -> None:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. "
                "Run: export OPENAI_API_KEY=your-key"
            )
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_completion_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


class OllamaProvider(LLMProvider):
    DEFAULT_MODEL = "qwen2.5:7b"

    def __init__(self, model: str | None = None) -> None:
        import openai
        self._client = openai.OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        )
        self._model = model or self.DEFAULT_MODEL

    def complete(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


def get_provider(name: str, model: str | None = None) -> LLMProvider:
    providers = {
        "claude": ClaudeProvider,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }
    cls = providers.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown provider '{name}'. Choose: claude, openai, ollama")
    return cls(model=model)
