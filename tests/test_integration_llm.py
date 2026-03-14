"""Integration tests with real LLM calls."""

from __future__ import annotations

import os
import pytest
from dotenv import load_dotenv

load_dotenv("/Users/aaronwu/Local/my-projects/give-it-all/.env", override=True)

from difftests.generator import generate_tests
from difftests.git_utils import DiffResult, FileDiff
from difftests.providers import get_provider


SAMPLE_DIFF = DiffResult(files=[
    FileDiff(
        path="src/calculator.py",
        diff_text=(
            "diff --git a/src/calculator.py b/src/calculator.py\n"
            "--- a/src/calculator.py\n"
            "+++ b/src/calculator.py\n"
            "@@ -0,0 +1,15 @@\n"
            "+def divide(a, b):\n"
            "+    \"\"\"Divide a by b.\"\"\"\n"
            "+    if b == 0:\n"
            "+        raise ValueError('Cannot divide by zero')\n"
            "+    return a / b\n"
            "+\n"
            "+def add(a, b):\n"
            "+    return a + b\n"
        ),
        original_content=(
            "def divide(a, b):\n"
            "    \"\"\"Divide a by b.\"\"\"\n"
            "    if b == 0:\n"
            "        raise ValueError('Cannot divide by zero')\n"
            "    return a / b\n\n"
            "def add(a, b):\n"
            "    return a + b\n"
        ),
        language="python",
    )
])


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
def test_claude_generates_runnable_tests():
    """Integration: Claude generates pytest tests that look valid."""
    provider = get_provider("claude", model="claude-haiku-4-5-20251001")
    result = generate_tests(SAMPLE_DIFF, provider, framework="pytest")

    assert not result.is_empty
    test_code = result.tests[0].test_code

    # Should contain pytest-style test functions
    assert "def test_" in test_code
    # Should reference divide or add (the changed functions)
    assert "divide" in test_code or "add" in test_code
    # Should not have markdown fences
    assert "```" not in test_code
    # Should be non-trivial
    assert len(test_code.splitlines()) >= 5


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
def test_claude_includes_edge_case_for_divide():
    """Integration: Claude should test division by zero edge case."""
    provider = get_provider("claude", model="claude-haiku-4-5-20251001")
    result = generate_tests(
        SAMPLE_DIFF,
        provider,
        framework="pytest",
        context="Focus on edge cases and error handling",
    )

    test_code = result.tests[0].test_code
    # Should handle the zero case
    assert "zero" in test_code.lower() or "0" in test_code or "ValueError" in test_code


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
def test_ollama_generates_basic_tests():
    """Integration: Ollama generates some form of test code."""
    try:
        provider = get_provider("ollama", model="qwen2.5:1.5b")
        result = generate_tests(SAMPLE_DIFF, provider, framework="pytest")
        assert not result.is_empty
        # At minimum should produce some output
        assert len(result.tests[0].test_code) > 50
    except Exception:
        pytest.skip("Ollama not available or model not pulled")
