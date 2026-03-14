"""Tests for the generator module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from difftests.generator import (
    GenerationResult,
    GeneratedTest,
    _build_system_prompt,
    _build_user_prompt,
    _detect_framework,
    _extract_code_from_response,
    generate_tests,
)
from difftests.git_utils import DiffResult, FileDiff


class TestExtractCodeFromResponse:
    def test_strips_python_fence(self):
        raw = "```python\ndef test_foo():\n    assert True\n```"
        assert _extract_code_from_response(raw) == "def test_foo():\n    assert True"

    def test_strips_plain_fence(self):
        raw = "```\ndef test_foo():\n    assert True\n```"
        assert _extract_code_from_response(raw) == "def test_foo():\n    assert True"

    def test_leaves_plain_code_unchanged(self):
        code = "def test_foo():\n    assert True"
        assert _extract_code_from_response(code) == code

    def test_strips_whitespace(self):
        raw = "  \n\ndef test_foo():\n    assert True\n\n  "
        assert _extract_code_from_response(raw) == "def test_foo():\n    assert True"


class TestDetectFramework:
    def test_uses_requested_framework(self):
        diff = FileDiff(path="a.py", diff_text="+", language="python")
        assert _detect_framework(diff, "unittest") == "unittest"

    def test_defaults_python_to_pytest(self):
        diff = FileDiff(path="a.py", diff_text="+", language="python")
        assert _detect_framework(diff, None) == "pytest"

    def test_defaults_js_to_jest(self):
        diff = FileDiff(path="a.js", diff_text="+", language="javascript")
        assert _detect_framework(diff, None) == "jest"

    def test_defaults_ts_to_vitest(self):
        diff = FileDiff(path="a.ts", diff_text="+", language="typescript")
        assert _detect_framework(diff, None) == "vitest"

    def test_defaults_go_to_go(self):
        diff = FileDiff(path="main.go", diff_text="+", language="go")
        assert _detect_framework(diff, None) == "go"

    def test_case_insensitive_request(self):
        diff = FileDiff(path="a.py", diff_text="+", language="python")
        assert _detect_framework(diff, "PYTEST") == "pytest"


class TestBuildSystemPrompt:
    def test_contains_pytest_instruction(self):
        prompt = _build_system_prompt("pytest", None)
        assert "pytest" in prompt.lower()

    def test_contains_context(self):
        prompt = _build_system_prompt("pytest", "auth module")
        assert "auth module" in prompt

    def test_no_context_when_none(self):
        prompt = _build_system_prompt("pytest", None)
        assert "Additional context" not in prompt


class TestBuildUserPrompt:
    def test_contains_diff_text(self):
        diff = FileDiff(
            path="src/auth.py",
            diff_text="+def login(): pass",
            language="python",
        )
        prompt = _build_user_prompt(diff)
        assert "+def login(): pass" in prompt
        assert "src/auth.py" in prompt

    def test_contains_original_content(self):
        diff = FileDiff(
            path="src/auth.py",
            diff_text="+def login(): pass",
            original_content="def login(): pass\n",
            language="python",
        )
        prompt = _build_user_prompt(diff)
        assert "def login(): pass" in prompt

    def test_truncates_large_diff(self):
        large_diff = "+" + "x" * 10000
        diff = FileDiff(path="a.py", diff_text=large_diff, language="python")
        prompt = _build_user_prompt(diff)
        # Should be truncated
        assert len(prompt) < len(large_diff) + 500


class TestGeneratedTest:
    def test_suggests_filename_for_python(self):
        test = GeneratedTest(
            source_path="src/auth.py",
            test_code="def test_foo(): pass",
            framework="pytest",
            language="python",
        )
        assert test.suggested_filename == "test_auth_test.py"

    def test_suggests_filename_for_js(self):
        test = GeneratedTest(
            source_path="src/utils.js",
            test_code="test('foo', () => {})",
            framework="jest",
            language="javascript",
        )
        assert test.suggested_filename == "test_utils.test.js"

    def test_custom_filename_not_overridden(self):
        test = GeneratedTest(
            source_path="src/auth.py",
            test_code="",
            framework="pytest",
            language="python",
            suggested_filename="my_test.py",
        )
        assert test.suggested_filename == "my_test.py"


class TestGenerationResult:
    def test_is_empty_with_no_tests(self):
        result = GenerationResult()
        assert result.is_empty is True

    def test_not_empty_with_tests(self):
        result = GenerationResult(tests=[
            GeneratedTest(source_path="a.py", test_code="", framework="pytest", language="python")
        ])
        assert result.is_empty is False


class TestGenerateTests:
    def test_generates_test_for_each_file(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "def test_foo():\n    assert True"

        diff = DiffResult(files=[
            FileDiff(path="a.py", diff_text="+def foo(): pass", language="python"),
            FileDiff(path="b.py", diff_text="+def bar(): pass", language="python"),
        ])

        result = generate_tests(diff=diff, provider=mock_provider)
        assert len(result.tests) == 2
        assert mock_provider.complete.call_count == 2

    def test_extracts_code_from_fenced_response(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "```python\ndef test_foo():\n    assert True\n```"

        diff = DiffResult(files=[
            FileDiff(path="a.py", diff_text="+def foo(): pass", language="python"),
        ])

        result = generate_tests(diff=diff, provider=mock_provider)
        assert "```" not in result.tests[0].test_code

    def test_returns_empty_for_empty_diff(self):
        mock_provider = MagicMock()
        diff = DiffResult()
        result = generate_tests(diff=diff, provider=mock_provider)
        assert result.is_empty is True
        mock_provider.complete.assert_not_called()

    def test_passes_context_to_provider(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "def test_x(): pass"

        diff = DiffResult(files=[
            FileDiff(path="a.py", diff_text="+x = 1", language="python"),
        ])

        generate_tests(diff=diff, provider=mock_provider, context="security-critical")
        system_prompt = mock_provider.complete.call_args[0][0]
        assert "security-critical" in system_prompt

    def test_model_label_stored_in_result(self):
        mock_provider = MagicMock()
        mock_provider.complete.return_value = "def test_x(): pass"

        diff = DiffResult(files=[
            FileDiff(path="a.py", diff_text="+x = 1", language="python"),
        ])

        result = generate_tests(diff=diff, provider=mock_provider, model_label="claude/haiku")
        assert result.model_label == "claude/haiku"
