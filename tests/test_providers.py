"""Tests for LLM providers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from difftests.providers import (
    ClaudeProvider,
    OllamaProvider,
    OpenAIProvider,
    get_provider,
)


class TestGetProvider:
    def test_returns_claude_provider(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic"):
                provider = get_provider("claude")
        assert isinstance(provider, ClaudeProvider)

    def test_returns_openai_provider(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI"):
                provider = get_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_returns_ollama_provider(self):
        with patch("openai.OpenAI"):
            provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_raises_for_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("unknown_ai")

    def test_case_insensitive(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic"):
                provider = get_provider("Claude")
        assert isinstance(provider, ClaudeProvider)


class TestClaudeProvider:
    def test_raises_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                ClaudeProvider()

    def test_complete_calls_api(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="def test_foo(): pass")]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic", return_value=mock_client):
                provider = ClaudeProvider()
                result = provider.complete("system", "user")

        assert result == "def test_foo(): pass"
        mock_client.messages.create.assert_called_once()

    def test_uses_custom_model(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic", return_value=mock_client):
                provider = ClaudeProvider(model="claude-custom")
                provider.complete("sys", "usr")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-custom"


class TestOpenAIProvider:
    def test_raises_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                OpenAIProvider()

    def test_complete_calls_api(self):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "def test_bar(): pass"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("openai.OpenAI", return_value=mock_client):
                provider = OpenAIProvider()
                result = provider.complete("system", "user")

        assert result == "def test_bar(): pass"


class TestOllamaProvider:
    def test_complete_returns_text(self):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "def test_ollama(): pass"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch("openai.OpenAI", return_value=mock_client):
            provider = OllamaProvider()
            result = provider.complete("system", "user")

        assert result == "def test_ollama(): pass"

    def test_uses_default_model(self):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        with patch("openai.OpenAI", return_value=mock_client):
            provider = OllamaProvider()
            assert provider._model == OllamaProvider.DEFAULT_MODEL
