"""Test generation logic using LLM providers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .git_utils import DiffResult, FileDiff
from .providers import LLMProvider


_FRAMEWORK_INSTRUCTIONS = {
    "pytest": (
        "Generate pytest tests using the pytest framework. "
        "Use `def test_...` functions. Import the module under test. "
        "Use `pytest.raises` for exception testing. "
        "Include fixtures where appropriate. "
        "Do NOT use unittest.TestCase."
    ),
    "unittest": (
        "Generate tests using Python's unittest.TestCase. "
        "Use `self.assert*` methods. Group related tests in classes."
    ),
    "jest": (
        "Generate Jest tests for JavaScript/TypeScript. "
        "Use `describe` and `it`/`test` blocks. "
        "Use `expect(...).toBe(...)` assertions. "
        "Mock dependencies with `jest.fn()` or `jest.mock()`."
    ),
    "vitest": (
        "Generate Vitest tests for JavaScript/TypeScript. "
        "Use `describe` and `it`/`test` blocks. "
        "Use `expect(...).toBe(...)` assertions. "
        "Import from 'vitest'."
    ),
    "rspec": (
        "Generate RSpec tests for Ruby. "
        "Use `describe` and `it` blocks with `expect(...).to` assertions."
    ),
    "go": (
        "Generate Go tests using the `testing` package. "
        "Use table-driven tests with `t.Run`. "
        "Name functions `Test...`. Import what you need."
    ),
}

_FRAMEWORK_FILE_SUFFIX = {
    "pytest": "_test.py",
    "unittest": "_test.py",
    "jest": ".test.js",
    "vitest": ".test.ts",
    "rspec": "_spec.rb",
    "go": "_test.go",
}

_DEFAULT_FRAMEWORK_BY_LANG = {
    "python": "pytest",
    "javascript": "jest",
    "typescript": "vitest",
    "ruby": "rspec",
    "go": "go",
}


@dataclass
class GeneratedTest:
    """Tests generated for a single file."""

    source_path: str
    test_code: str
    framework: str
    language: str
    suggested_filename: str = ""

    def __post_init__(self) -> None:
        if not self.suggested_filename:
            import os
            base = os.path.splitext(os.path.basename(self.source_path))[0]
            suffix = _FRAMEWORK_FILE_SUFFIX.get(self.framework, "_test.py")
            self.suggested_filename = f"test_{base}{suffix}"


@dataclass
class GenerationResult:
    """All generated tests from a run."""

    tests: list[GeneratedTest] = field(default_factory=list)
    model_label: str = ""

    @property
    def is_empty(self) -> bool:
        return len(self.tests) == 0


def _build_system_prompt(framework: str, context: str | None) -> str:
    framework_inst = _FRAMEWORK_INSTRUCTIONS.get(framework, _FRAMEWORK_INSTRUCTIONS["pytest"])
    base = (
        "You are an expert test engineer. Your task is to generate high-quality, "
        "runnable tests for changed code. Focus on:\n"
        "1. Testing the exact functions/methods that were added or modified\n"
        "2. Edge cases: empty inputs, None/null, boundary values, error conditions\n"
        "3. Happy path scenarios\n"
        "4. Any security-sensitive logic (auth, validation, SQL, etc.)\n\n"
        f"{framework_inst}\n\n"
        "IMPORTANT:\n"
        "- Output ONLY valid test code, no prose or explanations\n"
        "- Do not include markdown code fences (no ```)\n"
        "- Make tests self-contained with proper imports\n"
        "- Use descriptive test names that explain what is being tested\n"
        "- Mock external dependencies (databases, HTTP calls, file I/O) appropriately\n"
        "- If a function is pure, test it directly without mocks"
    )
    if context:
        base += f"\n\nAdditional context: {context}"
    return base


def _build_user_prompt(file_diff: FileDiff) -> str:
    parts = [
        f"Generate tests for the following changes to `{file_diff.path}`:",
        "",
        "## Git Diff (what changed):",
        "```diff",
        file_diff.diff_text[:6000],  # limit diff size
        "```",
    ]

    if file_diff.original_content:
        parts += [
            "",
            "## Current File Content (full context):",
            "```" + file_diff.language,
            file_diff.original_content[:4000],  # limit context
            "```",
        ]

    parts += [
        "",
        "Generate comprehensive tests covering the changed/added code.",
        "Output ONLY the test code, no explanations.",
    ]
    return "\n".join(parts)


def _extract_code_from_response(response: str) -> str:
    """Strip any markdown fences the LLM might have added."""
    # Remove ```python ... ``` or ``` ... ``` wrappers
    code = re.sub(r"^```[a-z]*\n?", "", response.strip(), flags=re.MULTILINE)
    code = re.sub(r"\n?```$", "", code.strip(), flags=re.MULTILINE)
    return code.strip()


def _detect_framework(file_diff: FileDiff, requested: str | None) -> str:
    if requested:
        return requested.lower()
    return _DEFAULT_FRAMEWORK_BY_LANG.get(file_diff.language, "pytest")


def generate_tests(
    diff: DiffResult,
    provider: LLMProvider,
    framework: str | None = None,
    context: str | None = None,
    model_label: str = "",
) -> GenerationResult:
    """Generate tests for all changed files in the diff."""
    results: list[GeneratedTest] = []

    for file_diff in diff.files:
        detected_framework = _detect_framework(file_diff, framework)
        system = _build_system_prompt(detected_framework, context)
        user = _build_user_prompt(file_diff)

        raw = provider.complete(system, user)
        test_code = _extract_code_from_response(raw)

        results.append(GeneratedTest(
            source_path=file_diff.path,
            test_code=test_code,
            framework=detected_framework,
            language=file_diff.language,
        ))

    return GenerationResult(tests=results, model_label=model_label)
